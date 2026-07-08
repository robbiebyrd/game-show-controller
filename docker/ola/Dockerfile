# syntax=docker/dockerfile:1
# Builds OLA 0.10.8 from the official GitHub release tarball.
# Targets arm64 (Raspberry Pi 4/5).
# To build on an amd64 host: docker buildx build --platform linux/arm64 .

ARG OLA_VERSION=0.10.8
ARG OLA_URL=https://github.com/OpenLightingProject/ola/releases/download/${OLA_VERSION}/ola-${OLA_VERSION}.tar.gz

# ── Build stage ───────────────────────────────────────────────────────────────
FROM --platform=linux/arm64 debian:bullseye-slim AS builder

ARG OLA_VERSION
ARG OLA_URL

RUN apt-get update && apt-get install -y --no-install-recommends \
    bison \
    ca-certificates \
    curl \
    flex \
    libcppunit-dev \
    libltdl-dev \
    libmicrohttpd-dev \
    libprotobuf-dev \
    libusb-1.0-0-dev \
    libtool \
    make \
    pkg-config \
    protobuf-compiler \
    python3-dev \
    python3-protobuf \
    uuid-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN curl -fsSL "${OLA_URL}" | tar xz --strip-components=1

RUN ./configure --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install DESTDIR=/install

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM --platform=linux/arm64 debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libltdl7 \
    libmicrohttpd12 \
    libprotobuf23 \
    libusb-1.0-0 \
    libuuid1 \
    python3 \
    python3-protobuf \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/usr/local /usr/local

RUN ldconfig \
    && useradd -r -s /bin/false ola \
    && mkdir -p /etc/ola \
    && chown ola:ola /etc/ola

USER ola

# 9090: OLA web UI   9010: olad RPC
EXPOSE 9090 9010

CMD ["olad", "--no-daemon", "--config-dir", "/etc/ola"]
