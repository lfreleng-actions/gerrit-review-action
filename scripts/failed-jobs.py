# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 The Linux Foundation
"""Print the errors block items for the failed jobs of this run attempt.

Run as 'python3 -I scripts/failed-jobs.py'. Reads its inputs from the
environment:

  GITHUB_API_URL      REST API root, e.g. https://api.github.com
  GITHUB_REPOSITORY   owner/repo
  GITHUB_RUN_ID       run to inspect
  GITHUB_RUN_ATTEMPT  attempt of that run
  GH_API_TOKEN        token with 'actions: read' and 'checks: read'
  ACT                 when set, print nothing and make no network call

Prints one '- <job name>: <message> ( <job URL> )' line per failure
annotation of each job whose conclusion is failure, timed_out or
cancelled, at most MAX_ITEMS of them, then '- ... and N more' when
there were others. Annotation text comes from the code under review,
so every item is one line with no control characters.

Never fails: any error prints a '::warning::' on stderr, nothing on
stdout, and exits 0, so the vote goes ahead without the block.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, TextIO

MAX_ITEMS = 10
MAX_MESSAGE_CHARS = 200
MAX_NAME_CHARS = 100
MAX_PAGES = 10
PER_PAGE = 100
TIMEOUT_SECONDS = 10
DEADLINE_SECONDS = 60
FAILED_CONCLUSIONS = {"failure", "timed_out", "cancelled"}
GENERIC_ANNOTATION = re.compile(r"^Process completed with exit code \d+\.$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NUMBER = re.compile(r"^[1-9][0-9]*$")
JOB_URL = re.compile(r"^https://\S+$")

Fetch = Callable[[str], Any]


class ApiError(Exception):
    """The API returned something this script cannot use."""


def clean(text: object, limit: int) -> str:
    """Collapse text to one line without control characters, capped."""
    if not isinstance(text, str):
        return ""
    kept = []
    for char in text:
        if char.isspace():
            kept.append(" ")
        elif unicodedata.category(char) not in ("Cc", "Cf"):
            kept.append(char)
    line = " ".join("".join(kept).split())
    if len(line) > limit:
        line = line[: limit - 3].rstrip() + "..."
    return line


def pages(fetch: Fetch, path: str, key: str | None) -> list[Any]:
    """Return every entry of a paginated listing.

    Raises ApiError when the listing runs past MAX_PAGES, so a partial
    result is never reported as the whole.
    """
    entries: list[Any] = []
    for page in range(1, MAX_PAGES + 1):
        body = fetch(f"{path}?per_page={PER_PAGE}&page={page}")
        batch = body.get(key) if key and isinstance(body, dict) else body
        if not isinstance(batch, list):
            raise ApiError(f"unexpected response from {path}")
        entries.extend(batch)
        if len(batch) < PER_PAGE:
            return entries
    raise ApiError(f"more than {MAX_PAGES} pages from {path}")


def job_items(fetch: Fetch, repo: str, job: Mapping[str, Any]) -> list[str]:
    """Return the errors block items for one failed job."""
    name = clean(job.get("name"), MAX_NAME_CHARS) or "unnamed job"
    url = clean(job.get("html_url"), 500)
    suffix = f" ( {url} )" if JOB_URL.match(url) else ""
    job_id = str(job.get("id", ""))
    if not NUMBER.match(job_id):
        raise ApiError("job without a numeric id")
    annotations = pages(fetch, f"/repos/{repo}/check-runs/{job_id}/annotations", None)
    messages = [
        clean(annotation.get("message"), MAX_MESSAGE_CHARS)
        for annotation in annotations
        if isinstance(annotation, dict)
        and annotation.get("annotation_level") == "failure"
    ]
    messages = [message for message in messages if message]
    specific = [m for m in messages if not GENERIC_ANNOTATION.match(m)]
    if specific:
        messages = specific
    if not messages:
        messages = ["failed"]
    return [f"- {name}: {message}{suffix}" for message in messages]


def collect_items(fetch: Fetch, repo: str, run_id: str, attempt: str) -> list[str]:
    """Return an item per failure annotation of the run attempt's failed jobs."""
    path = f"/repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs"
    items: list[str] = []
    for job in pages(fetch, path, "jobs"):
        if isinstance(job, dict) and job.get("conclusion") in FAILED_CONCLUSIONS:
            items.extend(job_items(fetch, repo, job))
    return items


def format_items(items: list[str]) -> list[str]:
    """Cap the items at MAX_ITEMS, counting the rest in a final line."""
    if len(items) <= MAX_ITEMS:
        return list(items)
    return [*items[:MAX_ITEMS], f"- ... and {len(items) - MAX_ITEMS} more"]


def api_fetcher(api_url: str, token: str) -> Fetch:
    """Return a fetch function for the REST API under a shared deadline."""
    deadline = time.monotonic() + DEADLINE_SECONDS

    def fetch(path: str) -> Any:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ApiError("timed out reading the run's jobs")
        request = urllib.request.Request(
            api_url.rstrip("/") + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        timeout = min(TIMEOUT_SECONDS, remaining)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    return fetch


def main(
    env: Mapping[str, str],
    fetch: Fetch | None = None,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    """Print the items, or warn and print nothing; always return 0."""
    if env.get("ACT"):
        return 0
    repo = env.get("GITHUB_REPOSITORY", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    attempt = env.get("GITHUB_RUN_ATTEMPT", "")
    api_url = env.get("GITHUB_API_URL", "")
    token = env.get("GH_API_TOKEN", "")
    try:
        if not (
            REPOSITORY.match(repo) and NUMBER.match(run_id) and NUMBER.match(attempt)
        ):
            raise ApiError("the run's repository, id or attempt is missing")
        if fetch is None:
            if not api_url.startswith("https://") or not token:
                raise ApiError("no API URL or token to read the run's jobs with")
            fetch = api_fetcher(api_url, token)
        lines = format_items(collect_items(fetch, repo, run_id, attempt))
    except Exception as error:  # noqa: BLE001 - the vote must go ahead
        # The type alone: an exception's text can quote the response.
        print(
            "::warning title=Errors block omitted::Could not read the failed"
            f" jobs of this run ({type(error).__name__}); the review carries"
            " no errors block. 'report-annotations' needs 'actions: read'"
            " and 'checks: read'.",
            file=err,
        )
        return 0
    for line in lines:
        print(line, file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(os.environ))
