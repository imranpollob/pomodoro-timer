#!/bin/sh
# Fix .deb dependencies emitted by @tauri-apps/cli 2.12.1 (latest stable).
#
# The bundler auto-detects `libgtk-3-0`, which does not exist on Ubuntu 24.04+,
# Linux Mint 22+ or Debian 13+ (64-bit time_t transition renamed it to
# libgtk-3-0t64 with no transitional package), so the .deb refuses to install.
# `bundle.linux.deb.depends` only extends the auto-detected list, it cannot
# remove the broken entry, and no newer stable CLI fixes the mapping.
#
# This script rewrites only the control archive in place, using alternates that
# install on both pre-t64 (Debian 12, Ubuntu 22.04) and t64 distributions, and
# adds the ALSA runtime the audio backend links against. The data archive is
# untouched, so file ownership and permissions are preserved. Idempotent.
#
# Usage: sh scripts/fix_deb_depends.sh target/release/bundle/deb/*.deb
set -eu

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <package.deb>..." >&2
  exit 2
fi

work=""
trap '[ -n "$work" ] && rm -rf "$work"' EXIT INT TERM

for deb in "$@"; do
  case "$deb" in
    /*) ;;
    *) deb="$PWD/$deb" ;;
  esac
  depends="$(dpkg-deb -f "$deb" Depends)"
  case "$depends" in
    *libgtk-3-0t64*)
      echo "$deb: already fixed"
      continue
      ;;
  esac
  case "$depends" in
    *libgtk-3-0*) ;;
    *)
      echo "$deb: expected libgtk-3-0 in Depends, got: $depends" >&2
      exit 1
      ;;
  esac
  work="$(mktemp -d)"
  control_member="$(ar t "$deb" | grep '^control\.tar\.' | head -n 1)"
  case "$control_member" in
    control.tar.zst) pack="zstd -19 -q -c" ;;
    control.tar.xz) pack="xz -c" ;;
    control.tar.gz) pack="gzip -9 -n -c" ;;
    *)
      echo "$deb: unsupported control member $control_member" >&2
      exit 1
      ;;
  esac
  (cd "$work" && ar x "$deb" "$control_member")
  mkdir -p "$work/control" && tar -xf "$work/$control_member" -C "$work/control"
  awk '
    /^Depends:/ {
      gsub(/libgtk-3-0,/, "libgtk-3-0t64 | libgtk-3-0,")
      sub(/libgtk-3-0$/, "libgtk-3-0t64 | libgtk-3-0")
      if ($0 !~ /libasound/) $0 = $0 ", libasound2t64 | libasound2"
    }
    { print }
  ' "$work/control/control" > "$work/control/control.new"
  mv "$work/control/control.new" "$work/control/control"
  (cd "$work/control" && tar -cf - .) | $pack > "$work/$control_member"
  (cd "$work" && ar r "$deb" "$control_member" >/dev/null)
  rm -rf "$work"
  work=""
  fixed="$(dpkg-deb -f "$deb" Depends)"
  case "$fixed" in
    *libgtk-3-0t64*) ;;
    *) echo "$deb: rewrite verification failed: $fixed" >&2; exit 1 ;;
  esac
  echo "$deb: Depends: $fixed"
done
