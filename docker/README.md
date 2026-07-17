# Docker Compose for local testing

This directory contains a [Docker Compose](https://docs.docker.com/compose/) setup for running a local [Concourse CI](https://concourse-ci.org/) environment for Pyknic testing.

## Overview

The Compose file [`local-tests-compose.yaml`](local-tests-compose.yaml) defines three services:

| Service | Description |
| --- | --- |
| `concourse-ci-psql` | PostgreSQL database used by Concourse for storing pipeline state and build logs |
| `concourse-ci` | The Concourse CI server (web + worker in `quickstart` mode) |
| `local-test` | A temporary container that runs the `fly` CLI to execute a pipeline test against the Concourse server |

All services are connected via the `concourse-ci-net` network and are isolated from the host. The only port accessible is `8080` for the Concourse web UI.

## Docker Compose services

### concourse-ci-psql

- **Build context**: [`./local-concourse-pgsql`](local-concourse-pgsql)
- **Ports**: none exposed to host

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
docker compose -f docker/local-tests-compose.yaml run \
  -e BRANCH=main \
  -e PYTHON_VERSION="3.13" \
  local-test
```

This will:

1. Build or pull the required images
2. Start PostgreSQL and Concourse
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
cd docker
docker compose -f local-tests-compose.yaml run -e BRANCH=main -e PYTHON_VERSION="3.13" local-test
```

### Running with different Python versions

```bash
docker compose -f docker/local-tests-compose.yaml run \
  -e BRANCH=feature/my-branch \
  -e PYTHON_VERSION="3.12" \
  local-test
```

### Accessing the Concourse UI

While the stack is running, open [http://localhost:8080](http://localhost:8080) in your browser and log in with:

- **Username**: `concourse`
- **Password**: `concourse`

## Related Files

| File | Description |
| --- | --- |
| [`local-tests-compose.yaml`](local-tests-compose.yaml) | Docker Compose service definitions |
| [`local-concourse-pgsql/Dockerfile`](local-concourse-pgsql/Dockerfile) | PostgreSQL image with Concourse schema initialization |
| [`local-concourse-pgsql/concourse_ci_init.sql`](local-concourse-pgsql/concourse_ci_init.sql) | SQL script to bootstrap the Concourse database |
| [`local-concourse-ci-fly/Dockerfile`](local-concourse-ci-fly/Dockerfile) | Image with `fly` CLI and test entrypoint |
| [`local-concourse-ci-fly/entrypoint.sh`](local-concourse-ci-fly/entrypoint.sh) | Entrypoint that waits for Concourse and runs the pipeline test |
| [`pyknic-concourse-base-image/Dockerfile`](pyknic-concourse-base-image/Dockerfile) | Base image used by the Concourse pipeline tasks themselves |
