#!/bin/bash

set -eux

DOCKER_REGISTRY="${DOCKER_REGISTRY:-localhost:5000}"
IMAGE_TAG="${IMAGE_TAG:-$(date '+%y%m%d-1')}"
DIR_NAME="$(dirname "$(realpath ${0})")"
DOCKER_SRC_DIR="${DIR_NAME}/pyknic"
REPACK_DIR="${DIR_NAME}/repack"
PKG_DIR="${DIR_NAME}/.."
TAR_REPACK="${TAR_REPACK:-}"  # if defined this makes docker cache works
# (pyknic sdist will have different hashes because of files attributes)

cd "${PKG_DIR}"
python setup.py sdist
cp -f dist/pyknic-*.tar.gz "${DOCKER_SRC_DIR}"

cd "${DIR_NAME}"
ls -al pyknic

if [[ -n "${TAR_REPACK}" ]]; then
  echo "sdist repacking"
  mkdir "${REPACK_DIR}"
  cd "${REPACK_DIR}"

  _PACKAGE="$(basename $(ls ${DOCKER_SRC_DIR}/pyknic-*.tar.gz))"
  echo "Package found -- ${_PACKAGE}"
  mv "${DOCKER_SRC_DIR}/${_PACKAGE}" .

  tar xvzf "${_PACKAGE}"
  rm "${_PACKAGE}"
  tar cvzf "${_PACKAGE}" --sort=name --no-acls --no-selinux --no-xattrs --mtime='UTC 1970-01-01' pyknic-*
  echo "Result of repacking: $(md5sum ${_PACKAGE} | awk '{print $1}')"

  mv "${_PACKAGE}" "${DOCKER_SRC_DIR}"
  cd "${DIR_NAME}"
  rm -rf "${REPACK_DIR}"
fi

docker build pyknic -t "${DOCKER_REGISTRY}/pyknic:${IMAGE_TAG}"
docker push "${DOCKER_REGISTRY}/pyknic:${IMAGE_TAG}"
