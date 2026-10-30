# file generated with AI assistance: Claude Code - 2026-10-20 22:27:51 UTC
# Software-rendering image for still renders of the game world: Godot
# under Xvfb with Mesa llvmpipe (OpenGL 4.5), no GPU needed.
# Build: make build   Run: ./render/render.sh (see render/render.sh)
FROM debian:bookworm-slim

# The Godot version lives here only; render.sh and the Makefile use the
# image, not the version.
ARG GODOT_VERSION=4.7.2

# xvfb + Mesa (llvmpipe) for the X11/OpenGL path; the X client libs are
# what Godot's x11 display server dlopens; mesa-utils for glxinfo probes;
# mesa-vulkan-drivers/libvulkan1 for a later lavapipe (Vulkan) attempt;
# time/procps for measurements.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      xvfb xauth libgl1-mesa-dri libgl1 libx11-6 libxcursor1 \
      libxinerama1 libxrandr2 libxrender1 libxi6 libxext6 \
      libxkbcommon0 libfontconfig1 libdbus-1-3 libudev1 \
      ca-certificates curl unzip time procps \
      mesa-utils mesa-vulkan-drivers libvulkan1 \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL --retry 5 --retry-all-errors -o /tmp/godot.zip \
      "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip" \
 && unzip -q /tmp/godot.zip -d /tmp/godot \
 && install -m 0755 \
      "/tmp/godot/Godot_v${GODOT_VERSION}-stable_linux.x86_64" \
      /usr/local/bin/godot \
 && rm -rf /tmp/godot /tmp/godot.zip \
 && godot --version

COPY entrypoint.sh /usr/local/bin/render-entrypoint
RUN chmod 0755 /usr/local/bin/render-entrypoint

WORKDIR /work
ENTRYPOINT ["/usr/local/bin/render-entrypoint"]
