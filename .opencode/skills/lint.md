# Lint Skill

## Description
Runs the full linting and formatting pipeline via pre-commit hooks.

## Instructions
**Always run `scripts/lint`** — this executes the full pre-commit hooks defined in `.pre-commit-config.yaml`, which includes both `ruff check` AND `ruff format` (plus YAML, whitespace, and end-of-file fixes).

### In the dev container:
```bash
docker exec <container_name> bash -c "cd /workspaces/ha-offdelay && bash scripts/lint"
```

### Locally (if dev container is not running):
```bash
bash scripts/lint
```

### To find the container name:
```bash
docker ps --filter "ancestor=mcr.microsoft.com/devcontainers/python:3.13" --format "{{.Names}}"
```

### What scripts/lint does:
- Runs `pre-commit run --all-files --show-diff-on-failure`
- This runs ALL hooks: ruff check, ruff format, check-yaml, trim-trailing-whitespace, fix-end-of-files
- If any hook fails, the script exits with an error and shows the diff

### Common fix:
If `ruff format` modifies files, the pre-commit hook will fail and show the diff. Just re-run `scripts/lint` after the files are auto-formatted.
