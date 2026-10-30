# file generated with AI assistance: Claude Code - 2026-10-22 16:30:00 UTC
# Export image for the CI build and `make export-image`: headless Godot with
# the release export templates for Linux, Windows and macOS (x86_64 and
# universal), nothing else.
# Build: make export-image   Use: make export and the CI export job
FROM debian:bookworm-slim

# No default: the version comes from the Makefile or the CI variable, so it
# is not pinned a third time here.
ARG GODOT_VERSION
RUN test -n "${GODOT_VERSION}" \
 || { echo "build with --build-arg GODOT_VERSION=<x.y.z>" >&2; exit 1; }

# libfontconfig1 and ca-certificates are what the headless editor binary
# needs at startup; zip packs the macOS .app for the artifact.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip zip libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL --retry 5 --retry-all-errors -o /tmp/godot.zip \
      "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip" \
 && unzip -q /tmp/godot.zip -d /tmp/godot \
 && install -m 0755 \
      "/tmp/godot/Godot_v${GODOT_VERSION}-stable_linux.x86_64" \
      /usr/local/bin/godot \
 && rm -rf /tmp/godot /tmp/godot.zip \
 && godot --version

# The .tpz holds every platform (about 1 GB); only the three release
# templates plus version.txt are extracted, which keeps the image small.
# unzip exits non-zero when a name is missing, so a renamed template fails
# the build here.
# XDG_DATA_HOME is fixed and world-writable (Godot creates user:// below it), so the templates are found
# whatever user and HOME the container runs with (the CI runs as root,
# `make export` as the host user).
ENV XDG_DATA_HOME=/opt/godot-data
ENV TEMPLATE_DIR=/opt/godot-data/godot/export_templates/${GODOT_VERSION}.stable
RUN curl -fsSL --retry 5 --retry-all-errors -o /tmp/templates.tpz \
      "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_export_templates.tpz" \
 && mkdir -p "${TEMPLATE_DIR}" \
 && unzip -q -j /tmp/templates.tpz \
      templates/version.txt \
      templates/linux_release.x86_64 \
      templates/windows_release_x86_64.exe \
      templates/macos.zip \
      -d "${TEMPLATE_DIR}" \
 && rm /tmp/templates.tpz \
 && chmod -R a+rwX /opt/godot-data \
 && ls -l "${TEMPLATE_DIR}"

WORKDIR /work
