# Unittest Skill

## Description
Runs pytest to execute unit tests inside the dev container.

## Instructions
Run pytest inside the dev container using `uv run`. First find the running container name, then execute:
```bash
docker exec <container_name> bash -c "cd /workspaces/offdelay-integration && uv run pytest"
```

To find the container name:
```bash
docker ps --filter "ancestor=mcr.microsoft.com/devcontainers/python:3.13" --format "{{.Names}}"
```
