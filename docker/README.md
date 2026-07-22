# Docker Compose for local testing

This directory contains a [Docker Compose](https://docs.docker.com/compose/) setup for running a local [Concourse CI](https://concourse-ci.org/) environment for Pyknic testing.

## Overview

The Compose file [`local-tests-compose.yaml`](local-tests-compose.yaml) defines four services:

| Service | Description |
| --- | --- |
| `git-server` | A lightweight Git repository server that serves project sources over HTTP for Concourse pipeline tests |
| `concourse-ci-psql` | PostgreSQL database used by Concourse for storing pipeline state and build logs |
| `concourse-ci` | The Concourse CI server (web + worker in `quickstart` mode) |
| `local-test` | A temporary container that runs the `fly` CLI to execute a pipeline test against the Concourse server |

All services are connected via the `concourse-ci-net` network and are isolated from the host. The only port accessible is `8080` for the Concourse web UI.

## Docker Compose services

### git-server

- **Build context**: [`./git-server`](git-server)
- **Static IP**: `172.10.0.10` — used by Concourse as the Git repository URI (`http://172.10.0.10:8000`)
- **Environment variables**:
  - `SOURCES_DIR` — path inside the container where host sources are mounted (default: `/sources`)
  - `BRANCH` — the Git branch name to create (default: `test-branch`)

### concourse-ci-psql

- **Build context**: [`./local-concourse-pgsql`](local-concourse-pgsql)

### concourse-ci

- **Image**: `concourse/concourse:7.13.2` (pinned by SHA256 digest)
- **Ports**: `8080:8080/tcp` — the Concourse web UI is available at `http://localhost:8080`
- **Credentials**: `concourse / concourse`

### local-test

- **Build context**: [`./local-concourse-ci-fly`](local-concourse-ci-fly)
- **Environment variables**:
  - `BRANCH` — the Git branch to test (e.g. `main`)
  - `PYTHON_VERSION` — the Python version to use (e.g. `3.13`)

## Usage

### Start all services and run a test

```bash
# From the project root (or the docker/ directory)
PYTHON_VERSION="3.13" LOCAL_FILES="$(pwd)" docker compose -f docker/local-tests-compose.yaml run local-test
```

This will:

1. Build or pull the required images
2. Start web-server (git), PostgreSQL and Concourse
3. Set up the pipeline and run test via `fly`

### Build images without running

```bash
docker compose -f docker/local-tests-compose.yaml build
```

### Stop and remove all containers

```bash
docker compose -f docker/local-tests-compose.yaml down
```

To also remove volumes (database data):

```bash
docker compose -f docker/local-tests-compose.yaml down -v
```

### Running from the project root

All commands above use `-f docker/local-tests-compose.yaml` so they can be run from the project root directory. Alternatively, you can `cd` into the `docker/` directory and omit the `-f` flag:

```bash
PYTHON_VERSION="3.13" LOCAL_FILES="$(pwd)" docker compose -f docker/local-tests-compose.yaml run local-test
```

### Running with different Python versions

```bash
PYTHON_VERSION="3.12" LOCAL_FILES="$(pwd)" docker compose -f docker/local-tests-compose.yaml run local-test
```

### Accessing the Concourse UI

While the stack is running, open [http://localhost:8080](http://localhost:8080) in your browser and log in with:

- **Username**: `concourse`
- **Password**: `concourse`

## Related Files

| File | Description |
| --- | --- |
| [`git-server/Dockerfile`](git-server/Dockerfile) | Debian-based image with Python HTTP server and Git |
| [`git-server/entrypoint.sh`](git-server/entrypoint.sh) | Entrypoint that creates a bare Git repo from bind-mounted sources and starts the HTTP server |
| [`local-concourse-ci-fly/Dockerfile`](local-concourse-ci-fly/Dockerfile) | Image with `fly` CLI and test entrypoint |
| [`local-concourse-ci-fly/entrypoint.sh`](local-concourse-ci-fly/entrypoint.sh) | Entrypoint that waits for Concourse and runs the pipeline test |
| [`local-concourse-pgsql/Dockerfile`](local-concourse-pgsql/Dockerfile) | PostgreSQL image with Concourse schema initialization |
| [`local-concourse-pgsql/concourse_ci_init.sql`](local-concourse-pgsql/concourse_ci_init.sql) | SQL script to bootstrap the Concourse database |
| [`local-tests-compose.yaml`](local-tests-compose.yaml) | Docker Compose service definitions |
| [`pyknic-concourse-base-image/Dockerfile`](pyknic-concourse-base-image/Dockerfile) | Base image used by the Concourse pipeline tasks themselves |
| [`pyknic-concourse-base-image/test-feedback.sh`](pyknic-concourse-base-image/test-feedback.sh) | Script that processes test results and provides feedback over Telegram |
