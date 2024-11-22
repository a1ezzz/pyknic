
FROM python:3.13.0@sha256:bc78d3c007f86dbb87d711b8b082d9d564b8025487e780d24ccb8581d83ef8b0

COPY pyknic-* /

COPY pyknic.ini /

RUN --mount=type=cache,target=/root/.cache/pip pip3 install --root-user-action=ignore "$(ls pyknic-*)[all]"

ENTRYPOINT ["python", "-m", "pyknic.pyknic", "-vv", "-c", "/pyknic.ini"]
