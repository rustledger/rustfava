#!/usr/bin/env bash
#
# Remove over-bundled system libraries from a Tauri-built AppImage.
#
# tauri-apps/tauri#15665: linuxdeploy's dependency follower sweeps
# libwayland-client and the glib/gstreamer family into usr/lib, and its
# excludelist does not cover them (the pkg2appimage community excludelist
# does, noting that bundling libwayland breaks newer Mesa). On a host whose
# Mesa is newer than the build machine's, the system EGL driver is loaded
# against the *bundled* libwayland-client, eglGetDisplay() returns
# EGL_BAD_PARAMETER, and WebKitWebProcess aborts — the window never appears
# and nothing useful reaches the user's terminal.
#
# Reported against rustfava as rustledger/rustfava#285 (Fedora 44, Mesa 25).
# The reporter's own workaround — LD_PRELOAD of the host libwayland-client —
# is the same mechanism seen from the other side.
#
# Upstream has no configuration surface for this: `bundle.linux.appimage.files`
# can only add files, not remove them, so post-processing is the only avenue
# until an `excludeLibraries`-style option exists.
set -euo pipefail

appimage="${1:?usage: strip-appimage-libs.sh <path/to/app.AppImage>}"
[ -f "$appimage" ] || { echo "::error::no AppImage at $appimage"; exit 1; }

# Infrastructure that must come from the host, not the bundle. Every entry is
# named in tauri#15665 as verified drop-in compatible with system versions.
PATTERNS=(
  'libwayland-*'      # the EGL breakage itself
  'libglib-2.0*' 'libgio-2.0*' 'libgobject-2.0*' 'libgmodule-2.0*'
  'libgst*'           # pulls in the glib family and its own plugin ABI
  'libmount*' 'libblkid*' 'libselinux*' 'libpcre2-8*'
  'libzstd*' 'libelf*' 'libffi*'
)

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
original="$(realpath "$appimage")"

cd "$workdir"
"$original" --appimage-extract >/dev/null

removed=0
for pattern in "${PATTERNS[@]}"; do
  while IFS= read -r lib; do
    rm -f "$lib"
    removed=$((removed + 1))
  done < <(find squashfs-root/usr/lib -maxdepth 1 -name "$pattern" 2>/dev/null)
done

if [ "$removed" -eq 0 ]; then
  # Either upstream fixed the excludelist or the layout moved. Either way the
  # silent no-op is the dangerous outcome, so say so.
  echo "::warning::no over-bundled libraries found in $appimage — has tauri#15665 been fixed, or did the AppDir layout change?"
fi

ARCH="${ARCH:-x86_64}" appimagetool --appimage-extract-and-run \
  squashfs-root "$original" >/dev/null

echo "stripped $removed over-bundled libraries from $(basename "$original")"
