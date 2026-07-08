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
    g++ \
    gcc \
    libftdi1-dev \
    libcppunit-dev \
    libltdl-dev \
    libmicrohttpd-dev \
    libprotobuf-dev \
    libprotoc-dev \
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
    libftdi1-2 \
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

# Ship opendmx/karate disabled by default so olad doesn't spam "No such file"
# for kernel DMX devices we never use. olad regenerates all other plugin configs
# on first run. NOTE: only applied when /etc/ola is a fresh (empty) volume.
COPY --chown=ola:ola plugin-config/ /etc/ola/

# olad refuses to run as root, so it runs unprivileged. Raw libusb access to the
# ENTTEC Open DMX USB (for the ftdidmx plugin) is granted on the host via a udev
# rule; see tools/deploy-pi.sh and docker-compose.yml.
USER ola

# 9090: OLA web UI   9010: olad RPC
EXPOSE 9090 9010

CMD ["olad", "--config-dir", "/etc/ola"]
