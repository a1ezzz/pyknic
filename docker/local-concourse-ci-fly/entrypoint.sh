#!/bin/bash

set -eu
set -o pipefail

PYTHON_VERSION="${PYTHON_VERSION:?}"
BRANCH="${BRANCH:?}"
REPO_URI="${REPO_URI:?}"
SOURCES_DIR="${SOURCES_DIR:?}"

CONCOURSE_HOST="${CONCOURSE_HOST:?}"
CONCOURSE_USER="${CONCOURSE_USER:?}"
CONCOURSE_PASS="${CONCOURSE_PASS:?}"

_RETRIES=30
_SLEEP=5

_CONCOURSE_TARGET="local"
_CONCOURSE_PIPELINE_NAME="main-pipeline"
_CONCOURSE_PIPELINE_FILE="${SOURCES_DIR}/concourse-ci/pyknic-test.yml"
_JOB_NAME="pyknic-test-job-py-${PYTHON_VERSION}"

# ------------------------------------------------------------------
# Wait for web to be ready
# ------------------------------------------------------------------
echo "==> Waiting for Concourse web to be ready..."
for i in $(seq 1 ${_RETRIES}); do

    echo "    Attempt ${i}/${_RETRIES}..."

    if curl -sf "http://${CONCOURSE_HOST}/api/v1/info" > /dev/null 2>&1; then
        echo "    Concourse web is ready."
        break
    fi

    if [ "${i}" -eq "${_RETRIES}" ]; then
        echo "ERROR: Concourse web did not start in time."
        exit 1
    fi

    sleep ${_SLEEP}
done

# ------------------------------------------------------------------
# Log in to fly and set the pipeline
# ------------------------------------------------------------------

echo "==> Logging in with fly..."

fly --target "${_CONCOURSE_TARGET}" login \
    --concourse-url "http://${CONCOURSE_HOST}" \
    --username "${CONCOURSE_USER}" \
    --password "${CONCOURSE_PASS}" \
    --team-name "main"

echo "==> Setting pipeline: ${_CONCOURSE_PIPELINE_NAME}"
fly --target "${_CONCOURSE_TARGET}" set-pipeline \
    --non-interactive \
    --pipeline "${_CONCOURSE_PIPELINE_NAME}" \
    --var "branch=${BRANCH}" \
    --var "github-access-token=" \
    --var "pull_request_id=" \
    --var "commit=" \
    --var "pull_request_branch_name=" \
    --var "extra_branch=${BRANCH}" \
    --var "python_version=${PYTHON_VERSION}" \
    --var "tg_bot_token=" \
    --var "tg_chat=" \
    --var "tg_api_host=" \
    --var "pytest_s3_test_uri=" \
    --var "repo_uri=${REPO_URI}" \
    --config "${_CONCOURSE_PIPELINE_FILE}"

echo "==> Unpausing pipeline..."
fly --target "${_CONCOURSE_TARGET}" unpause-pipeline \
    --pipeline "${_CONCOURSE_PIPELINE_NAME}"

echo ""
echo "============================================================"
echo "  Concourse CI is running!"
echo "  URL:      ${CONCOURSE_HOST}"
echo "  Pipeline: ${_CONCOURSE_PIPELINE_NAME}"
echo "  Branch:   ${BRANCH}"
echo "  Python:   ${PYTHON_VERSION}"
echo "============================================================"
echo ""


# ------------------------------------------------------------------
# Trigger the pipeline job
# ------------------------------------------------------------------

echo "==> Triggering job: ${_JOB_NAME}"
_JOB_REQUEST_TXT="$(fly --target "${_CONCOURSE_TARGET}" trigger-job \
    --job "${_CONCOURSE_PIPELINE_NAME}/${_JOB_NAME}"
)"
echo ${_JOB_REQUEST_TXT}

_JOB_REQUEST_ID=$(echo "${_JOB_REQUEST_TXT}" | grep -P -o '^[^#]+#\K([0-9]+)')

echo "==> Watching job: ${_JOB_NAME}"
set +e  # watch may return with non-zero exit code
fly --target "${_CONCOURSE_TARGET}" watch \
    --job "${_CONCOURSE_PIPELINE_NAME}/${_JOB_NAME}" \
    --build "${_JOB_REQUEST_ID}"
set -e

# ------------------------------------------------------------------
# Capture the build result
# ------------------------------------------------------------------

echo "==> Checking build status..."
_BUILD_OUTPUT=$(fly --target "${_CONCOURSE_TARGET}" builds \
    --pipeline "${_CONCOURSE_PIPELINE_NAME}" \
    --json 2>/dev/null
)

echo ""
echo "============================================================"
echo "  Pipeline finished!"
echo "  URL:      ${CONCOURSE_HOST}"
echo "  Pipeline: ${_CONCOURSE_PIPELINE_NAME}"
echo "  Job:      ${_JOB_NAME}"
echo "  Status:   $(echo "${_BUILD_OUTPUT}" | jq ".[] | select(.name == \"${_JOB_REQUEST_ID}\")" | jq -r ".status")"
echo "  Branch:   ${BRANCH}"
echo "  Python:   ${PYTHON_VERSION}"
echo "============================================================"
echo ""

echo "==> Build details..."
echo "${_BUILD_OUTPUT}" | jq ".[] | select(.name == \"${_JOB_REQUEST_ID}\")"


echo "==> All done."
