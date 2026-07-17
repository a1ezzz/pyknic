
FROM "debian:trixie-slim@sha256:020c0d20b9880058cbe785a9db107156c3c75c2ac944a6aa7ab59f2add76a7bd"

ARG CONCOURSE_VERSION
ARG CONCOURSE_PIPELINE_URL="https://raw.githubusercontent.com/a1ezzz/pyknic/refs/heads/main/concourse-ci/pyknic-test.yml"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download fly CLI matching the Concourse version
RUN curl -sSL "https://github.com/concourse/concourse/releases/download/v${CONCOURSE_VERSION}/fly-${CONCOURSE_VERSION}-linux-amd64.tgz" \
    | tar -xz -C /usr/local/bin/ fly

RUN curl -sSL "${CONCOURSE_PIPELINE_URL}" > /concourse-pipeline.yml

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
