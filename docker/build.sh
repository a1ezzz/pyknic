#!/bin/bash

set -eux

DOCKER_REGISTRY="${DOCKER_REGISTRY:-localhost:5000}"
IMAGE_TAG="${IMAGE_TAG:-$(date '+%y%m%d-1')}"
DIR_NAME="$(dirname "${0}")"
DOCKER_SRC_DIR="${DIR_NAME}/pyknic"
PKG_DIR="${DIR_NAME}/.."

cd "${PKG_DIR}"
python setup.py sdist
cp -f dist/pyknic-* "${DOCKER_SRC_DIR}"

cd "${DIR_NAME}"
docker build pyknic -t "${DOCKER_REGISTRY}/pyknic:${IMAGE_TAG}"
docker push "${DOCKER_REGISTRY}/pyknic:${IMAGE_TAG}"
