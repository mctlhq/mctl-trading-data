# Contributing to mctl-trading-data

Thank you for your interest in contributing to mctl-trading-data! This guide will help you get started.

## Prerequisites

- **Python 3.12+**
- **Docker** (for container builds)

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

The service is an MCP server over streamable HTTP — see `README.md` for the
tool surface and auth model.

## Testing

Run unit tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

Please ensure both pass before submitting a pull request.

## Pull Request Process

1. Create a feature branch (`feat/...`, `fix/...`, `chore/...`) — never commit to `main` directly
2. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, ...)
3. Open a pull request; CI and an automated review must pass before merge

## Code Style

- English for all code, comments, and documentation
- No emoji in code or commit messages

## Reporting Issues

Open a GitHub issue with a clear description and reproduction steps where applicable.

## Security Issues

Please do NOT open public issues for security vulnerabilities — see [SECURITY.md](SECURITY.md).
