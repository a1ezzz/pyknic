# Pyknic

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Code Style](https://img.shields.io/badge/code%20style-flake8%20%2F%20mypy-black)](https://github.com/a1ezzz/pyknic)

**Pyknic** is a modular Python application framework and toolkit designed for background task scheduling, distributed operations, secure RPC command execution, and unified storage/backup management.

It includes:
- **`pyknic-server`** — an event-driven server daemon managing multithreaded task pipelines, schedulers, and FastAPI-based services.
- **`bellboy`** — a feature-rich CLI utility and client for server interaction, remote command execution, secure backups, and data replication.
- **`pyknic.lib`** — a comprehensive library of reusable modules for asynchronous I/O, unified storage access (Local, SFTP, AWS S3), cryptography, scheduling, and authentication.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
  - [1. Running the Server (`pyknic-server`)](#1-running-the-server-pyknic-server)
  - [2. Using the CLI Client (`bellboy`)](#2-using-the-cli-client-bellboy)
- [Core Library Modules](#core-library-modules)
- [Development and Testing](#development-and-testing)
  - [Running Unit Tests](#running-unit-tests)
  - [Local CI with Docker Compose](#local-ci-with-docker-compose)
  - [Linting and Type Checking](#linting-and-type-checking)
- [License](#license)

---

## Key Features

### ⏱️ Task Scheduler & Execution Engine
- **Flexible Scheduling**: Execute tasks immediately, sequentially in chains (`ChainedTasksSource`), or periodically (`CronTasksSource`).
- **Thread Management**: Thread-safe task execution using `ThreadedTask`, `ThreadExecutor`, and execution priority queues.

### 🌐 FastAPI Server & Lobby RPC
- **Integrated Server**: Built on top of FastAPI and Uvicorn with dynamic sub-application registration.
- **Lobby RPC API**: Secure command dispatch system supporting arbitrary registered operations with typed validation.
- **Asymmetric Security**: RSA-signed JSON Web Tokens (JWT) with configurable audience, leeway, TTL, and response signing.
- **Pluggable AAA**: Multiple authentication providers including `htpasswd` (Argon2, BCrypt, SHA-512) and static bearer tokens.

### 🧰 `bellboy` CLI Tool
- **Server Control**: Execute server-side commands such as `ping` and `resources` remotely.
- **Session Management**: Authenticate using `login` (`basic`, `token`, `trust`) and store credentials in secure secret backends (`shm` or OS `keyring`).
- **Flexible Formatting**: Output results in human-friendly Rich terminal tables or structured JSON (`-f json`).

### 📦 Unified Storage & Backup System
- **Unified Storage Interface (`IOClientProto`)**: Consistent API for interacting with `Local`, `SFTP` (Paramiko), `S3` (Boto3), and `VirtualDir` storage targets.
- **Bandwidth Throttling**: Asynchronous read/write throttling with `IOThrottler`.
- **Streaming Compression**: Native compression support for `gzip`, `bz2`, `lzma`, and `zstandard`.
- **`archive_v1` Backup Format**: Chunked, encrypted, and compressed backup archives created from files or command outputs directly to remote destinations.

### 🔐 Cryptographic Primitives
- RSA keypair generation, serialization, signature creation, and verification.
- Symmetric encryption (AES) and Key Derivation Functions (Argon2, PBKDF2, scrypt).
- Apache `htpasswd` parser with constant-time hash comparisons.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |               bellboy                 |
                      |    (CLI Client / Standalone Tool)     |
                      +-------------------+-------------------+
                                          |
                              REST / JSON | RSA-Signed JWT
                                          v
+---------------------------------------------------------------------------------+
|                                 pyknic-server                                   |
|                                                                                 |
|  +--------------------+     +---------------------+     +--------------------+  |
|  |     Scheduler      | <-> |       Datalog       | <-> |   FastAPI Server   |  |
|  |  (Cron / Chained)  |     |  (State & Signals)  |     |   (Uvicorn/Lobby)  |  |
|  +--------------------+     +---------------------+     +--------------------+  |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

## Installation

### Prerequisites
- Python **3.11**, **3.12**, **3.13**, or **3.14**

### Install from Source

Clone the repository and install the package:

```bash
git clone https://github.com/a1ezzz/pyknic.git
cd pyknic

# Install base package
pip install .

# Or install in editable mode with development & testing dependencies
pip install -e ".[all]"
```

Available extra requirement targets:
- `dev`: Development tools (`twine`, `Babel`, `watchdog`).
- `test`: Testing and linting suite (`pytest`, `pytest-cov`, `flake8`, `mypy`, type stubs).
- `all`: Combines both `dev` and `test`.

---

## Configuration

Pyknic uses YAML configuration files supporting environment variable expansions (e.g. `${VAR:-default}`).

Default application settings are loaded from package templates and can be merged with external configuration files or directories:

```yaml
# config.yaml example
pyknic:
  apps:
    - "fastapi-init"       # Enable FastAPI server task

  fastapi:
    uvicorn_host: 0.0.0.0
    uvicorn_port: 8000
    swagger: yes           # Enable Swagger UI (/docs)
    apps:
      - "lobby"            # Enable Lobby RPC endpoint

    lobby:
      main_url_path: /api/v1/lobby
      private_key_default_size: 4096
      jwt:
        algorithm: "RS256"
        audience: "pyknic::lobby::user"
        ttl: 1800
      aaa_policies:
        admin_policy:
          provider: "htpasswd"
          file: "/etc/pyknic/htpasswd"
          allowed_commands:
            - "ping"
            - "resources"
            - "backup"
```

Configuration files can be specified via CLI arguments (`-c`, `-C`) or environment variables:
- `PYKNIC_APP_FILE_CONFIG`: Path to a single YAML configuration file.
- `PYKNIC_APP_DIR_CONFIG`: Path to a directory containing configuration files to merge.

---

## Quick Start

### 1. Running the Server (`pyknic-server`)

Start the `pyknic-server` daemon with your custom configuration:

```bash
# Basic run with info-level logging (-vv)
pyknic-server -c config.yaml -vv

# Verbosity flags:
# -v: WARNING
# -vv: INFO
# -vvv: DEBUG
```

When started, the daemon boots up the scheduler, registers configured background tasks, and launches the FastAPI HTTP server.

---

### 2. Using the CLI Client (`bellboy`)

The `bellboy` utility provides CLI commands to manage sessions, interact with remote servers, and perform operations.

#### Authenticate & Manage Sessions

```bash
# Login via HTTP Basic / htpasswd
bellboy login \
  --server.lobby-url http://127.0.0.1:8000/api/v1/lobby \
  --server.secret-backend shm \
  --authentication basic \
  --login admin \
  --secret.direct "my-secret-password"

# List active stored credentials
bellboy list-logins --secret-backend shm

# Discard active session
bellboy logout \
  --server.lobby-url http://127.0.0.1:8000/api/v1/lobby \
  --server.secret-backend shm
```

#### Ping and Server Diagnostics

```bash
# Ping the remote lobby server
bellboy ping --server.lobby-url http://127.0.0.1:8000/api/v1/lobby

# Inspect server resource consumption (CPU, memory, threads)
bellboy resources --server.lobby-url http://127.0.0.1:8000/api/v1/lobby

# Output in JSON format
bellboy -f json resources --server.lobby-url http://127.0.0.1:8000/api/v1/lobby
```

#### File Synchronization & Replication (`copier`)

Copy files across local filesystems, SFTP, and AWS S3 with throttling support:

```bash
# Copy from local filesystem to remote SFTP with 1 MB/s throttling
bellboy copier \
  --source 'file:///var/data/archive.tar.gz' \
  --destination sftp://backupuser@192.168.1.50/var/backups/archive.tar.gz \
  --throttling 1048576

# Copy from S3 bucket to local directory
bellboy copier \
  --source s3://my-bucket/database.dump \
  --destination 'file:///local/backups/database.dump'
```

#### Secure Encrypted Backups (`backup`)

Create compressed and encrypted backups (`archive_v1` format) directly to remote targets:

```bash
# Backup directory tree to an S3 bucket with Zstandard compression
bellboy backup \
  --files /var/www/html /etc/nginx \
  --destination s3://my-backups/nginx-www.archive \
  --compression zstandard \
  --password "strong-passphrase"
```

---

## Core Library Modules

Pyknic provides several standalone, modular packages under `pyknic.lib`:

| Module | Description |
| --- | --- |
| `pyknic.lib.tasks` | Core task scheduling engine (`Scheduler`, `ChainedTasksSource`, `CronTasksSource`, `ThreadedTask`) |
| `pyknic.lib.io.clients` | Unified storage clients: `IOLocalClient`, `IOSftpClient`, `IOS3Client`, `IOVirtualClient` |
| `pyknic.lib.io.aio_wrapper` | Non-blocking async wrappers and I/O rate throttler (`IOThrottler`) |
| `pyknic.lib.crypto` | Cryptographic utilities: RSA keys, AES ciphers, Argon2/PBKDF2 KDFs, and Apache `htpasswd` |
| `pyknic.lib.backup` | Archive specification (`archive_v1`) supporting compression, hash trees, and encryption |
| `pyknic.lib.registry` | Generic registry pattern decorator (`@register_api`) for pluggable extensions |
| `pyknic.lib.fastapi` | FastAPI AAA integration, JWT validation models, and Telegram Bot protocol structures |

---

## Development and Testing

### Running Unit Tests

Run the test suite with coverage reporting:

```bash
pytest
```

HTML coverage reports are generated automatically under `docs/pytest/` and `docs/pytest-coverage/`.

### Local CI with Docker Compose

Pyknic provides a self-contained local [Concourse CI](https://concourse-ci.org/) environment using Docker Compose:

```bash
# Run tests against Python 3.13 in isolated Concourse pipeline
PYTHON_VERSION="3.13" LOCAL_FILES="$(pwd)" docker compose -f docker/local-tests-compose.yaml run local-test

# Or run against Python 3.12
PYTHON_VERSION="3.12" LOCAL_FILES="$(pwd)" docker compose -f docker/local-tests-compose.yaml run local-test
```

While the stack is running, access the Concourse web UI at [http://localhost:8080](http://localhost:8080) (`concourse` / `concourse`).

To clean up containers and volumes:

```bash
docker compose -f docker/local-tests-compose.yaml down -v
```

See [`docker/README.md`](docker/README.md) and [`concourse-ci/README.md`](concourse-ci/README.md) for further CI documentation.

### Linting and Type Checking

Enforce code formatting and type safety:

```bash
# Check PEP8 style compliance
flake8

# Run static type checks
mypy pyknic
```

---

## License

This project is licensed under the GNU General Public License v3 - see the [LICENSE](LICENSE) file for details.
