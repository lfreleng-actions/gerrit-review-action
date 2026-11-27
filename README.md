<!--
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# 🔍 Gerrit Review Action

Set review votes and comments on a Gerrit system via SSH. This action allows
automated CI/CD workflows to provide feedback on Gerrit changes by posting
votes, comments, and status updates.

## gerrit-review-action

## Usage Example

<!-- markdownlint-disable MD046 -->

```yaml
steps:
  - name: "Set Gerrit review vote"
    uses: lfreleng-actions/gerrit-review-action@main
    with:
      host: "gerrit.example.com"
      username: "ci-bot"
      key: ${{ secrets.GERRIT_SSH_KEY }}
      known_hosts: ${{ secrets.GERRIT_KNOWN_HOSTS }}
      gerrit-change-number: "12345"
      gerrit-patchset-number: "1"
      vote-type: "success"
```

<!-- markdownlint-enable MD046 -->

## Inputs

<!-- markdownlint-disable MD013 -->

| Name                   | Required | Default        | Description                                                                                                              |
| ---------------------- | -------- | -------------- | ------------------------------------------------------------------------------------------------------------------------ |
| host                   | True     |                | The Gerrit host with SSH available (accepts a bare hostname or `host:port`; an embedded port overrides the `port` input) |
| port                   | False    | "29418"        | The SSH port to use                                                                                                      |
| username               | True     |                | The username to connect to the Gerrit host as                                                                            |
| key                    | True     |                | The SSH private key to use                                                                                               |
| key_name               | False    | "id_rsa"       | The filename for the key                                                                                                 |
| known_hosts            | True     |                | The known hosts for the host server                                                                                      |
| gerrit-change-number   | True     |                | The Gerrit Change Number to vote on                                                                                      |
| gerrit-patchset-number | False    | "1"            | The patchset number of the change                                                                                        |
| vote-type              | False    | "clear"        | Vote type: clear, success, failure, cancelled                                                                            |
| comment-only           | False    | "false"        | Post comment without voting                                                                                              |
| message                | False    | ""             | Text appended to the review comment (newlines allowed, other control characters rejected; see [Size limit](#size-limit)) |
| closed-change          | False    | "warn"         | On a closed change: `warn` posts the result as a comment and succeeds; `fail` fails the step                             |
| report-annotations     | False    | "false"        | `"true"` adds an `ERRORS:` block from the run's failed jobs to a `failure` or `cancelled` vote (see [Errors](#errors))   |
| github-token           | False    | `github.token` | Token used to read the run's jobs and annotations; needs `actions: read` and `checks: read`                              |
| trailers               | False    | ""             | Newline-separated `Key: value` lines appended as the last block (see [Trailers](#trailers))                              |

<!-- markdownlint-enable MD013 -->

## Outputs

<!-- markdownlint-disable MD013 -->

| Name          | Description                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------------- |
| change-closed | `"true"` when Gerrit refused the review because the change had already closed, else `"false"`  |

<!-- markdownlint-enable MD013 -->

## Vote Types

The action supports four different vote types:

### clear

- **Vote**: Verified=0, Code-Review=0
- **Usage**: Reset/clear existing votes on a change
- **Status Message**: "STARTED"

### success

- **Vote**: Verified=+1
- **Usage**: Mark the change as verified/passing
- **Status Message**: "SUCCESS"

### failure

- **Vote**: Verified=-1
- **Usage**: Mark the change as failing verification
- **Status Message**: "FAILURE"

### cancelled

- **Vote**: Verified=-1, Code-Review=-1
- **Usage**: Mark the workflow run as cancelled/aborted (inconclusive result)
- **Status Message**: "CANCELLED"

## Comment Mode

When `comment-only` is `"true"`, the action posts a status comment
without applying votes. This provides informational updates
without affecting the review workflow.

## Closed Changes

A Gerrit change can merge, or its owner can abandon it, while its CI
is still running. When the action then votes, Gerrit refuses with one
of:

<!-- write-good reads Gerrit's first reply as passive voice; the
     entity renders as a plain space and keeps the reply verbatim. -->
<!-- markdownlint-disable MD033 -->

<pre><code>error: fatal: change is&#32;closed
fatal: one or more reviews failed; review output above
</code></pre>

<!-- markdownlint-enable MD033 -->

```text
error: fatal: Cannot reduce vote on labels for closed change: Verified
```

Nothing is wrong with the change or the CI: the vote arrived too late
to matter. Gerrit still accepts a comment on a closed change, so with
`closed-change: "warn"` (the default) the action:

1. Sends the same review again without labels, unless `comment-only`
   is already `"true"`, so the result still reaches the change.
2. Emits a `Change already closed` warning naming the change and
   patchset, saying whether the comment reached Gerrit.
3. Succeeds, and sets the `change-closed` output to `"true"`.

The action matches either reply without regard to case. Set
`closed-change: "fail"` to fail the step instead, as earlier releases
did. Any other SSH or Gerrit failure fails the step under both
settings. A `closed-change` value other than `warn` or `fail` fails
the step before any SSH connection opens.

## Custom Message

The `message` input appends caller-supplied text to the review
comment, so a comment can say what a run did as well as how it ended.
The status line and run URL stay first, followed by a blank line and
the message. Leaving `message` empty posts the same comment as before.

A merge pipeline reporting its outcome on the merged change:

<!-- markdownlint-disable MD046 -->

```yaml
steps:
  - name: "Report merge outcome"
    uses: lfreleng-actions/gerrit-review-action@main
    with:
      host: ${{ vars.GERRIT_SERVER }}
      username: ${{ vars.GERRIT_SSH_USER }}
      key: ${{ secrets.GERRIT_SSH_PRIVKEY }}
      known_hosts: ${{ vars.GERRIT_KNOWN_HOSTS }}
      gerrit-change-number: ${{ inputs.GERRIT_CHANGE_NUMBER }}
      gerrit-patchset-number: ${{ inputs.GERRIT_PATCHSET_NUMBER }}
      vote-type: "success"
      comment-only: "true"
      message: >-
        ${{ needs.merge.outputs.has_release == 'true'
        && format('Released {0} to nexus.',
        needs.merge.outputs.release_version)
        || format('Snapshot {0} published to nexus.
        No release file, nothing released.',
        needs.merge.outputs.snapshot_version) }}
```

<!-- markdownlint-enable MD046 -->

The comment Gerrit shows:

```text
SUCCESS: https://github.com/{owner}/{repo}/actions/runs/{run_id}
JOB:     Gerrit Merge [gerrit-merge.yaml]

Released 1.1.1 to nexus.
```

The action treats the message as untrusted text:

- It reaches the shell through `env:`, never through the `run:`
  body, and the step never evaluates it.
- It travels to Gerrit as one single-quoted argument, with embedded
  quotes escaped for Gerrit's SSH command parser. Quotes, `$()`,
  backticks, `;` and backslashes arrive as literal text.
- A message carrying a control character other than newline (tab,
  carriage return, escape sequences), or too long for the review
  (see [Size limit](#size-limit)), fails the step before any SSH
  connection opens.
- The action drops trailing newlines, such as the one a `|` block
  scalar adds.

## Message Format

Gerrit prepends `Patch Set N: <votes>` and a blank line itself; the
action writes what follows. One blank line separates the blocks below,
in this order, and an absent block leaves no gap:

1. **Status line**: `<STATUS>: <run URL>`, where `STATUS` is one of
   `STARTED`, `SUCCESS`, `FAILURE` or `CANCELLED`.
2. **Job line**, directly under the status line: `JOB:`, the
   workflow's name, then its file name in square brackets. Spaces
   after `JOB:` start the value in the column of the URL above.
3. **Message**: the `message` input, when set.
4. **Errors**: `ERRORS:` followed by one item per line, when
   `report-annotations` asks for them (see [Errors](#errors)).
5. **Trailers**: the `trailers` input, when set.

<!-- markdownlint-disable MD013 -->

```text
FAILURE: https://github.com/onap/cps/actions/runs/41021621001
JOB:     Gerrit Verify [gerrit-verify.yaml]

ERRORS:
- Maven Build/Test / Build: Tests run: 412, Failures: 1 ( https://github.com/onap/cps/actions/runs/41021621001/job/123 )

Verify-Run: 41021621001
```

<!-- markdownlint-enable MD013 -->

The name comes from `github.workflow` and the file name from the base
name of the path in `github.workflow_ref`; inside this composite
action both describe the calling workflow. A workflow without `name:`
reports its path as its name, so the job line shows the file name
without its extension instead. The action strips control characters
from the name, and drops the brackets when it cannot derive the file
name or the name does not match `^[A-Za-z0-9._-]+$`.

Consumers reading messages through Gerrit's REST API may rely on the
first two lines:

```text
line 1: ^(STARTED|SUCCESS|FAILURE|CANCELLED): (\S+)$
line 2: ^JOB:\s+(.+?)(?: \[([A-Za-z0-9._-]+)\])?$
```

### Tag

Each review carries the tag `autogenerated:github:<workflow file>`,
for example `autogenerated:github:gerrit-verify.yaml`, or
`autogenerated:github` when the action cannot derive the file name. The
`autogenerated:` prefix keeps Gerrit treating the message as a bot's;
the suffix lets a REST consumer select one workflow's messages
without parsing their text. Earlier releases tagged every review
`autogenerated:github`, so a consumer matching that tag exactly
needs to match the prefix instead.

### Size limit

The whole comment, every block above, holds at most 4096 bytes. The
status and job lines, the message and the trailers must fit within it
together, or the step fails before any SSH connection opens; the
errors block takes what room remains (see [Errors](#errors)).

### Errors

With `report-annotations: "true"` and a `failure` or `cancelled`
vote, the action lists the jobs of this run attempt whose conclusion
is `failure`, `timed_out` or `cancelled`, and adds one item per
failure annotation of each:

```text
- <job name>: <message> ( <job URL> )
```

- A job with other failure annotations loses the generic
  `Process completed with exit code N.` one; a job with none shows
  `failed`.
- Annotation text comes from the code under review, so the action
  collapses each message to one line, strips control characters and
  caps it at 200 characters. Every item starts with `-`, so no
  annotation can forge a status line, job line or trailer.
- The block holds at most 10 items, then `- ... and N more`. When the
  comment would exceed 4096 bytes, the action drops items, counting
  them in that last line, or leaves the block out.
- Reading the annotations never fails the step. A missing permission,
  an API error, a timeout or a listing longer than 1,000 entries
  emits a warning and the review goes without the block, rather than
  a partial one. Under ACT the action makes no network call.

The job needs these permissions for its `github-token`:

<!-- markdownlint-disable MD013 -->

| Permission      | Endpoint                                                                     |
| --------------- | ---------------------------------------------------------------------------- |
| `actions: read` | `GET /repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs`    |
| `checks: read`  | `GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations`            |

<!-- markdownlint-enable MD013 -->

### Trailers

`trailers` takes newline-separated `Key: value` lines and appends
them as the last block. Each line must match
`^[A-Za-z][A-Za-z0-9-]*: \S.*$` and hold no control character other
than newline, and the trailers must fit the
[size limit](#size-limit). Anything else fails the step before any
SSH connection opens. The action drops trailing newlines, such as the
one a `|` block scalar adds.

A vote job using the three inputs:

<!-- markdownlint-disable MD046 -->

```yaml
vote:
  needs: [build]
  if: ${{ always() }}
  runs-on: ubuntu-latest
  permissions:
    actions: read
    checks: read
  steps:
    - name: "Report the result"
      uses: lfreleng-actions/gerrit-review-action@main
      with:
        host: ${{ vars.GERRIT_SERVER }}
        username: ${{ vars.GERRIT_SSH_USER }}
        key: ${{ secrets.GERRIT_SSH_PRIVKEY }}
        known_hosts: ${{ vars.GERRIT_KNOWN_HOSTS }}
        gerrit-change-number: ${{ inputs.GERRIT_CHANGE_NUMBER }}
        gerrit-patchset-number: ${{ inputs.GERRIT_PATCHSET_NUMBER }}
        vote-type: >-
          ${{ needs.build.result == 'success' && 'success'
          || needs.build.result == 'cancelled' && 'cancelled'
          || 'failure' }}
        report-annotations: "true"
        trailers: |
          Verify-Run: ${{ github.run_id }}
```

<!-- markdownlint-enable MD046 -->

## SSH Configuration

The action requires SSH access to the Gerrit server. You must provide:

1. **SSH Private Key**: Store in GitHub secrets (e.g., `GERRIT_SSH_KEY`)
2. **Known Hosts**: The SSH fingerprint for the Gerrit server
3. **Username**: The Gerrit username for the CI account
4. **Host**: The Gerrit server hostname

The `host` input also accepts a `host:port` shorthand (for example,
`modeseven.org:40086`), which suits callers that keep the Gerrit
endpoint in a single repository variable. When `host` carries an
embedded port (matching `name:digits`), the action splits it and uses
that port in place of the `port` input. Plain hostnames pass through
verbatim and the action honours the explicit `port` input.

The action also accepts bare IPv6 literals (e.g. `host: ::1`)
and uses the default `port: 29418` unless you override it. The
action does **not** support bracketed IPv6 forms such as
`[::1]:29418`; pass the bare address in `host` and the port in
`port` instead.

The action automatically configures SSH with the provided credentials and
accepts legacy SSH-RSA key types for compatibility with Gerrit servers.

## Implementation Details

The action performs the following steps:

1. **Vote Preparation**: Determines the appropriate vote and status based on
   the `vote-type` input, reads the failed jobs' annotations when
   `report-annotations` asks for them (`scripts/failed-jobs.py`), and
   composes, validates and quotes the comment
   (`scripts/compose-review.sh`). Invalid input fails here, before any
   SSH setup.
2. **SSH Setup**: Installs the provided SSH key and configures connection
3. **Gerrit Review**: Executes the `gerrit review` command with:
   - Change and patchset numbers
   - Appropriate vote labels (if not comment mode)
   - Status and job lines, plus any message, errors and trailers
   - `autogenerated:github:<workflow file>` tag for tracking
   (`scripts/send-review.sh`), retrying without labels when the change
   has closed (see [Closed Changes](#closed-changes))

## Status Messages

All reviews include a status message linking back to the GitHub Actions run:

```text
{STATUS}: https://github.com/{owner}/{repo}/actions/runs/{run_id}
JOB:     {workflow name} [{workflow file}]
```

A non-empty `message`, the errors block and `trailers` follow, each
after a blank line (see [Message Format](#message-format)).

This provides traceability between Gerrit reviews and the CI/CD pipeline that
generated them.

## Notes

- The action skips SSH operations when running in ACT (local testing),
  but still composes and validates the review command
- All reviews include an `autogenerated:github:<workflow file>` tag for
  identification (see [Tag](#tag))
- The action supports both legacy and modern SSH key types
- Default SSH port 29418 is commonly used by Gerrit servers
