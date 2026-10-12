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

| Name                   | Required | Default  | Description                                                                                                              |
| ---------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| host                   | True     |          | The Gerrit host with SSH available (accepts a bare hostname or `host:port`; an embedded port overrides the `port` input) |
| port                   | False    | "29418"  | The SSH port to use                                                                                                      |
| username               | True     |          | The username to connect to the Gerrit host as                                                                            |
| key                    | True     |          | The SSH private key to use                                                                                               |
| key_name               | False    | "id_rsa" | The filename for the key                                                                                                 |
| known_hosts            | True     |          | The known hosts for the host server                                                                                      |
| gerrit-change-number   | True     |          | The Gerrit Change Number to vote on                                                                                      |
| gerrit-patchset-number | False    | "1"      | The patchset number of the change                                                                                        |
| vote-type              | False    | "clear"  | Vote type: clear, success, failure, cancelled                                                                            |
| comment-only           | False    | "false"  | Post comment without voting                                                                                              |
| message                | False    | ""       | Text appended to the review comment (max 4096 bytes; newlines allowed, other control characters rejected)                |

<!-- markdownlint-enable MD013 -->

## Outputs

This action does not produce any outputs.

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

Released 1.1.1 to nexus.
```

The action treats the message as untrusted text:

- It reaches the shell through `env:`, never through the `run:`
  body, and the step never evaluates it.
- It travels to Gerrit as one single-quoted argument, with embedded
  quotes escaped for Gerrit's SSH command parser. Quotes, `$()`,
  backticks, `;` and backslashes arrive as literal text.
- Messages longer than 4096 bytes, or carrying a control character
  other than newline (tab, carriage return, escape sequences),
  fail the step before any SSH connection opens.
- The action drops trailing newlines, such as the one a `|` block
  scalar adds.

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
   the `vote-type` input, and validates and quotes the optional `message`
   (`scripts/review-command.sh`). Invalid input fails here, before any SSH
   setup.
2. **SSH Setup**: Installs the provided SSH key and configures connection
3. **Gerrit Review**: Executes the `gerrit review` command with:
   - Change and patchset numbers
   - Appropriate vote labels (if not comment mode)
   - Status message with GitHub Actions run URL, plus any custom message
   - `autogenerated:github` tag for tracking

## Status Messages

All reviews include a status message linking back to the GitHub Actions run:

```text
{STATUS}: https://github.com/{owner}/{repo}/actions/runs/{run_id}
```

A non-empty `message` adds a blank line and the message below it (see
[Custom Message](#custom-message)).

This provides traceability between Gerrit reviews and the CI/CD pipeline that
generated them.

## Notes

- The action skips SSH operations when running in ACT (local testing),
  but still composes and validates the review command
- All reviews include the `autogenerated:github` tag for identification
- The action supports both legacy and modern SSH key types
- Default SSH port 29418 is commonly used by Gerrit servers
