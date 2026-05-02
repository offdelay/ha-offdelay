# Lint Skill

## Description
Runs the ruff linter and formatter on the codebase.

## Instructions
Run the linting script inside the dev container. First find the running container name, then execute:
```bash
docker exec <container_name> bash -c "cd /workspaces/offdelay-integration && scripts/lint"
```

To find the container name:
```bash
docker ps --filter "ancestor=mcr.microsoft.com/devcontainers/python:3.13" --format "{{.Names}}"
```
