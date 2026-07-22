#!/bin/bash

set -eu
set -o pipefail

REPO_DIR="${REPO_DIR:?}"
WORKDIR="${WORKDIR:?}"
SOURCES_DIR="${SOURCES_DIR:?}"
BRANCH="${BRANCH:?}"

# ------------------------------------------------------------------
# Create a bare git repository
# ------------------------------------------------------------------

echo "==> Starting initialization..."

WORKTREE="${WORKDIR}/worktree"

echo "==> Configuring default branch: ${BRANCH}"
git config --global init.defaultBranch "${BRANCH}"

echo "==> Configuring commit author"
git config --global user.email "john-doe@docker-image"
git config --global user.name "John Doe-Docker"

echo "==> Removing existing repository at ${REPO_DIR}"
rm -rf "${REPO_DIR}"

echo "==> Creating bare repository at ${REPO_DIR}"
git init --bare "${REPO_DIR}" --initial-branch="${BRANCH}"

echo "==> Creating temporary worktree"
mkdir -p "${WORKTREE}"
cleanup() {
    echo "==> Cleaning up temporary worktree"
    rm -rf "${WORKTREE}"

    echo "==> Cleaning up repo directory"
    rm -rf "${REPO_DIR}"
}
trap cleanup EXIT

# ------------------------------------------------------------------
# Populate a repository
# ------------------------------------------------------------------

echo "==> Cloning git repository into a worktree"
git clone "${REPO_DIR}" "${WORKTREE}"

echo "==> Copying sources from ${SOURCES_DIR} to worktree"

cd "${WORKTREE}"
mv "${WORKTREE}/.git" "${WORKTREE}/.base_git"
cp -r "${SOURCES_DIR}/." "${WORKTREE}/"
rm -rf "${WORKTREE}/.git"
mv "${WORKTREE}/.base_git" "${WORKTREE}/.git"

echo "==> Appending files"
git add -A

echo "==> Creating initial commit"
git commit -m "Initial commit from volume source"

echo "==> Pushing to origin/${BRANCH}"
git push --force origin "${BRANCH}"

# ------------------------------------------------------------------
# Start a web server
# ------------------------------------------------------------------

echo "==> Update repo internal files"

cd "${REPO_DIR}"
git update-server-info

echo "==> Start web-server"
exec python3 -m http.server
