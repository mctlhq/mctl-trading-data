# mctl-trading-data — Development Rules

## Commit Conventions
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`
- Subject under 72 characters
- Body explains WHY, not WHAT
- Do NOT add `Co-Authored-By:` trailers

## Versioning
- Semver, NO `v` prefix in tags: `0.1.0`, not `v0.1.0`
- Image tag mirrors git tag: `ghcr.io/mctlhq/mctl-trading-data:0.1.0`
- Release commit: `chore: release x.y.z`

## Branches
- `main` is always deployable
- Feature branches: `feat/<short-desc>` or `fix/<short-desc>`
- Merge commits (no-ff, no squash): `gh pr merge <N> --merge --delete-branch`

## PR review
- Request both bots: `@claude review` + `@copilot review`
- Merge gate: at least ONE bot clean (no P1/P2)
- CI must be green

## Code style
- No emoji in code/commits/docs unless explicitly requested
- English for code, comments, docs
- Default to no comments — only when WHY is non-obvious
- Prefer editing existing files over creating new ones
- `secrets.compare_digest` for any token comparison
