
# in order to build with other version call this: docker build --build-arg BASE_PYTHON_VERSION=3.12 ...
ARG BASE_PYTHON_VERSION=3.11

FROM python:${BASE_PYTHON_VERSION}-alpine AS builder

# this makes cache hotter!
RUN mkdir -p /pip-cache && pip3 --cache-dir /pip-cache install virtualenv mypy pyknic && mypy --install-types --non-interactive

FROM python:${BASE_PYTHON_VERSION}-alpine

RUN apk add --no-cache curl git bash jq

COPY --from=builder /pip-cache /pip-cache

COPY test-feedback.sh /scripts/test-feedback.sh
