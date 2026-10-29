#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 The Linux Foundation

# Send the composed 'gerrit review' command to Gerrit over SSH, and
# handle a change that merged or was abandoned before the vote arrived.
#
# Reads its inputs from the environment, so the calling step never
# interpolates a templated value into shell code:
#
#   TARGET_HOST             SSH destination (validated by the caller)
#   REVIEW_COMMAND          review to send, from review-command.sh
#   COMMENT_COMMAND         the same review without labels; required
#                           when COMMENT_ONLY is 'false'
#   COMMENT_ONLY            'false' when REVIEW_COMMAND applies labels
#   CLOSED_CHANGE           'warn' or 'fail'
#   GERRIT_CHANGE_NUMBER    positive integer
#   GERRIT_PATCHSET_NUMBER  positive integer
#   GITHUB_OUTPUT           receives 'change-closed=true|false'
#
# Gerrit refuses a vote on a closed change with 'change is closed' or
# 'Cannot reduce vote on labels for closed change', but still accepts
# a comment. With CLOSED_CHANGE=warn, such a refusal retries the review
# without labels (unless it carried none), emits a warning and exits
# 0. With CLOSED_CHANGE=fail, and for any other failure, the script
# exits with the status ssh returned.

set -euo pipefail

fail() {
  echo "::error::$*" >&2
  exit 1
}

warn() {
  echo "::warning title=Change already closed::$*"
}

set_output() {
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "change-closed=$1" >> "${GITHUB_OUTPUT}"
  fi
}

# Never echo CLOSED_CHANGE: a newline in it could forge a workflow
# command in the log.
closed_change="${CLOSED_CHANGE:-}"
case "${closed_change}" in
  warn | fail) ;;
  *) fail "Refusing to use closed-change: expected warn or fail" ;;
esac

change="${GERRIT_CHANGE_NUMBER:-}"
patchset="${GERRIT_PATCHSET_NUMBER:-}"
if [[ ! "${change}" =~ ^[1-9][0-9]*$ ]] \
  || [[ ! "${patchset}" =~ ^[1-9][0-9]*$ ]]; then
  fail "Refusing to send review: change and patchset numbers must be" \
    "positive integers"
fi
if [[ -z "${TARGET_HOST:-}" ]] || [[ -z "${REVIEW_COMMAND:-}" ]]; then
  fail "Refusing to send review: TARGET_HOST and REVIEW_COMMAND must be set"
fi
if [[ "${COMMENT_ONLY:-}" == "false" ]] && [[ -z "${COMMENT_COMMAND:-}" ]]; then
  fail "Refusing to send review: COMMENT_COMMAND must be set"
fi

errors="$(mktemp)"
trap 'rm -f "${errors}"' EXIT

# Send one review. Its stderr lands in ${errors} for inspection and
# is copied to the log.
send() {
  local status=0
  # '--' stops OpenSSH parsing a leading '-' in the destination as an
  # option, whatever validation the caller has done.
  ssh -- "${TARGET_HOST}" "$1" 2> "${errors}" || status=$?
  cat "${errors}" >&2
  return "${status}"
}

status=0
send "${REVIEW_COMMAND}" || status=$?
if (( status == 0 )); then
  set_output false
  exit 0
fi

if ! grep -qiE 'change is closed|for closed change' "${errors}"; then
  set_output false
  exit "${status}"
fi

set_output true
if [[ "${closed_change}" == "fail" ]]; then
  exit "${status}"
fi

target="change ${change} patchset ${patchset}"
if [[ "${COMMENT_ONLY:-}" != "false" ]]; then
  warn "Gerrit refused the review on ${target} because the change has" \
    "closed; the result did not reach the change."
elif send "${COMMENT_COMMAND}"; then
  warn "Gerrit refused the vote on ${target} because the change has" \
    "closed; posted the result as a comment instead of a vote."
else
  warn "Gerrit refused the vote on ${target} because the change has" \
    "closed, and the comment-only retry failed too; the result did" \
    "not reach the change."
fi
exit 0
