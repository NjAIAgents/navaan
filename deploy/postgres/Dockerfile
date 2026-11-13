# postgres:17-alpine with pgvector 0.8.1 built in. Same Alpine (musl) base as before,
# so text sort order and existing indexes do not change. Used by navaan, vidlasso, whodunit.
FROM postgres:17-alpine
ARG PGVECTOR_VERSION=v0.8.1
RUN apk add --no-cache --virtual .build-deps git build-base \
 && git clone --branch ${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
 && cd /tmp/pgvector && make OPTFLAGS="" with_llvm=no && make with_llvm=no install \
 && cd / && rm -rf /tmp/pgvector && apk del .build-deps
