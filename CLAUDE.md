# CLAUDE.md

## Dependencies

All runtime and dev dependencies must be declared in `pyproject.toml`. Do not add dependency lists to `tox.ini` or other tool config files.

## Commits

- Each commit must represent a single logical change — do not bundle unrelated modifications.
- Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.

Examples:
```
feat(cli): add --output-dir flag to stems command
fix(midi): correct off-by-one in note duration calculation
docs(readme): update installation instructions
chore(deps): bump demucs to 4.1.0
```
