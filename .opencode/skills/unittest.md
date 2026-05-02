# Unittest Skill

## Description
Runs pytest to execute unit tests inside the dev container.

## Instructions
Run pytest inside the dev container using `uv run`. First find the running container name, then execute:
```bash
docker exec <container_name> bash -c "cd /workspaces/ha-offdelay && uv run pytest"
```

To find the container name:
```bash
docker ps --filter "ancestor=mcr.microsoft.com/devcontainers/python:3.13" --format "{{.Names}}"
```

If tests fail with a `.venv` error like `failed to create directory .venv: File exists`, remove it first:
```bash
docker exec <container_name> bash -c "cd /workspaces/ha-offdelay && rm -rf .venv && uv run pytest"
```

## Post-test: Always run lint
After tests pass, always run `scripts/lint` to catch formatting issues:
```bash
docker exec <container_name> bash -c "cd /workspaces/ha-offdelay && bash scripts/lint"
```
