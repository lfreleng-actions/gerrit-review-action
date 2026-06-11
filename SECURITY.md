<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 The Linux Foundation
-->

# Security Policy

This document describes the security policy for this repository, including
which versions receive security updates and how to report vulnerabilities.

## Supported Versions

Maintainers develop and merge security fixes on the default branch
(`main`) and publish those fixes in the latest tagged release. Older
releases and tags do not receive security updates. Users should track
the latest tagged release for security patches.

| Version               | Supported          |
| --------------------- | ------------------ |
| Latest tagged release | :white_check_mark: |
| Older releases/tags   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it
**privately** so that maintainers can investigate and release a fix before
the issue becomes publicly known.

### Preferred: GitHub Private Vulnerability Reporting

Use GitHub's private vulnerability reporting feature:

1. Navigate to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Provide as much detail as possible (see below).

This creates a private advisory visible to maintainers.

### Alternative: Email

If you cannot use GitHub's private reporting, send an email to the Linux
Foundation Release Engineering team at:

- **<releng@linuxfoundation.org>**

Please do **not** report security vulnerabilities through public GitHub
issues, discussions, or pull requests.

### What to Include

To help maintainers triage and resolve the report, please include:

- A clear description of the vulnerability and its potential impact.
- Steps to reproduce the issue (proof-of-concept code or commands).
- The affected version(s), commit SHA, or release tag.
- Any known mitigations or workarounds.
- Your name and contact details for follow-up (optional).

## Response Process

Maintainers will acknowledge receipt of vulnerability reports within
**5 business days**. We aim to:

1. Confirm the vulnerability and determine its severity.
2. Develop and test a fix in a private branch or advisory.
3. Coordinate a disclosure timeline with the reporter.
4. Release a patched version and publish a security advisory.

We follow a responsible disclosure process and credit reporters in the
published advisory unless they request to remain anonymous.

## Scope

This policy covers the source code, configuration, and documentation
in this repository. Please report vulnerabilities in upstream
dependencies to their respective maintainers; this project will update
affected dependencies once fixes become available.
