
FROM debian:trixie-slim@sha256:020c0d20b9880058cbe785a9db107156c3c75c2ac944a6aa7ab59f2add76a7bd

EXPOSE 8000

ENV SOURCES_DIR="/sources"
ENV GIT_BRANCH="main"
ENV WORKDIR="/workdir"
ENV REPO_DIR="${WORKDIR}/git/repo.git"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh

RUN mkdir ${SOURCES_DIR} && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
