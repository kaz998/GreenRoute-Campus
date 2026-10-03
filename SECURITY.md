# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability.

Instead, contact the project maintainer privately through the contact method configured on the GitHub repository. Include enough information to reproduce the issue safely.

Do not include real API keys, passwords, authentication cookies, or private user data in a report.

## Local secrets

- Keep `OPENAI_API_KEY` in `.env` only.
- Never commit `.env`, credentials, production databases, or private exports.
- Rotate a key immediately if it is accidentally exposed.
