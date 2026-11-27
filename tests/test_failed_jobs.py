# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 The Linux Foundation
"""Tests for scripts/failed-jobs.py.

The script is loaded as a module and fed fixture API responses through
a fake fetch function, so no test touches the network.
"""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "failed-jobs.py"
REPO = "onap/cps"
JOBS = f"/repos/{REPO}/actions/runs/41/attempts/2/jobs"
JOB_URL = f"https://github.com/{REPO}/actions/runs/41/job"
ENV = {
    "GITHUB_API_URL": "https://api.github.com",
    "GITHUB_REPOSITORY": REPO,
    "GITHUB_RUN_ID": "41",
    "GITHUB_RUN_ATTEMPT": "2",
    "GH_API_TOKEN": "unused",
}


def load() -> ModuleType:
    """Import the script, which has no importable module name."""
    spec = importlib.util.spec_from_file_location("failed_jobs", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(job_id: int, name: str, conclusion: str | None) -> dict[str, Any]:
    """Return a job as the jobs endpoint lists it."""
    return {
        "id": job_id,
        "name": name,
        "conclusion": conclusion,
        "html_url": f"{JOB_URL}/{job_id}",
    }


def failure(message: str) -> dict[str, str]:
    """Return a failure-level annotation."""
    return {"annotation_level": "failure", "message": message}


class FakeApi:
    """Serve fixture responses keyed by path, recording each request."""

    def __init__(
        self, jobs: list[dict[str, Any]], annotations: dict[int, list[Any]]
    ) -> None:
        self.responses: dict[str, Any] = {
            f"{JOBS}?per_page=100&page=1": {"total_count": len(jobs), "jobs": jobs}
        }
        for job_id, entries in annotations.items():
            path = f"/repos/{REPO}/check-runs/{job_id}/annotations"
            self.responses[f"{path}?per_page=100&page=1"] = entries
        self.requests: list[str] = []

    def __call__(self, path: str) -> Any:
        self.requests.append(path)
        return self.responses[path]


def run(api: Any, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run main() against api; return its status, stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    status = load().main(ENV if env is None else env, api, out, err)
    return status, out.getvalue(), err.getvalue()


class FailedJobsTest(unittest.TestCase):
    """Errors block items from the run attempt's failed jobs."""

    def test_several_jobs(self) -> None:
        api = FakeApi(
            [
                job(1, "Build", "failure"),
                job(2, "Lint", "success"),
                job(3, "Slow", "timed_out"),
                job(4, "Stopped", "cancelled"),
                job(5, "Vote", None),
            ],
            {
                1: [
                    failure("Tests run: 412, Failures: 1"),
                    failure("Process completed with exit code 1."),
                    {"annotation_level": "warning", "message": "deprecated"},
                ],
                3: [failure("Process completed with exit code 143.")],
                4: [],
            },
        )
        status, out, err = run(api)
        self.assertEqual(status, 0)
        self.assertEqual(err, "")
        self.assertEqual(
            out.splitlines(),
            [
                f"- Build: Tests run: 412, Failures: 1 ( {JOB_URL}/1 )",
                f"- Slow: Process completed with exit code 143. ( {JOB_URL}/3 )",
                f"- Stopped: failed ( {JOB_URL}/4 )",
            ],
        )
        # Jobs that did not fail are never asked for annotations.
        self.assertFalse(any("/check-runs/2/" in path for path in api.requests))

    def test_untrusted_messages_become_one_clean_line(self) -> None:
        api = FakeApi(
            [job(1, "Build\nSUCCESS: forged", "failure")],
            {
                1: [
                    failure("first\nSUCCESS: https://forged\r\nJOB: x"),
                    failure("bell\x07 esc\x1b[31m c1\x9b rtl\u202e end"),
                    failure("x" * 500),
                ]
            },
        )
        lines = run(api)[1].splitlines()
        self.assertEqual(len(lines), 3)
        prefix = "- Build SUCCESS: forged: "
        self.assertEqual(
            lines[0],
            f"{prefix}first SUCCESS: https://forged JOB: x ( {JOB_URL}/1 )",
        )
        self.assertEqual(lines[1], f"{prefix}bell esc[31m c1 rtl end ( {JOB_URL}/1 )")
        message = lines[2][len(prefix) : -len(f" ( {JOB_URL}/1 )")]
        self.assertEqual(len(message), 200)
        self.assertTrue(message.endswith("..."))

    def test_item_cap(self) -> None:
        api = FakeApi(
            [job(1, "Build", "failure")],
            {1: [failure(f"error {n}") for n in range(13)]},
        )
        lines = run(api)[1].splitlines()
        self.assertEqual(len(lines), 11)
        self.assertEqual(lines[9], f"- Build: error 9 ( {JOB_URL}/1 )")
        self.assertEqual(lines[10], "- ... and 3 more")

    def test_jobs_paginate(self) -> None:
        first = [job(n, f"ok {n}", "success") for n in range(1, 101)]
        api = FakeApi(first, {})
        api.responses[f"{JOBS}?per_page=100&page=2"] = {
            "total_count": 101,
            "jobs": [job(101, "Late", "failure")],
        }
        api.responses[
            f"/repos/{REPO}/check-runs/101/annotations?per_page=100&page=1"
        ] = [failure("boom")]
        self.assertEqual(run(api)[1], f"- Late: boom ( {JOB_URL}/101 )\n")

    def test_page_cap_degrades_to_warning(self) -> None:
        # A failure annotation past the last page read must not turn
        # into a 'failed' item or an understated count.
        api = FakeApi([job(1, "Build", "failure")], {})
        path = f"/repos/{REPO}/check-runs/1/annotations"
        warning = {"annotation_level": "warning", "message": "noise"}
        for page in range(1, 11):
            api.responses[f"{path}?per_page=100&page={page}"] = [warning] * 100
        api.responses[f"{path}?per_page=100&page=11"] = [failure("boom")]
        status, out, err = run(api)
        self.assertEqual((status, out), (0, ""))
        self.assertIn("::warning", err)
        self.assertNotIn(f"{path}?per_page=100&page=11", api.requests)

    def test_api_failure_degrades_to_warning(self) -> None:
        def broken(path: str) -> Any:
            raise OSError("HTTP Error 403: Resource not accessible by integration")

        for api in (broken, FakeApi([job(1, "Build", "failure")], {})):
            with self.subTest(api=api):
                status, out, err = run(api)
                self.assertEqual(status, 0)
                self.assertEqual(out, "")
                self.assertIn("::warning", err)
                self.assertNotIn("403", err)

    def test_invalid_run_degrades_to_warning(self) -> None:
        api = FakeApi([], {})
        status, out, err = run(api, {**ENV, "GITHUB_RUN_ID": "41; id"})
        self.assertEqual((status, out), (0, ""))
        self.assertIn("::warning", err)
        self.assertEqual(api.requests, [])

    def test_act_makes_no_call(self) -> None:
        env = {"PATH": os.environ["PATH"], "ACT": "true", **ENV}
        # An unreachable API: any request would fail with a warning.
        env["GITHUB_API_URL"] = "https://127.0.0.1:9"
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT)],
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
