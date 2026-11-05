#!/usr/bin/env bash
set -euo pipefail
mkdir -p package-cores third-party-notices
for SYSTEM in NES SNES; do
  if [ "$SYSTEM" = NES ]; then REPO=libretro/libretro-fceumm; REV=e0f3086a8104f8fbbe49a2615b10401504a9533f; DIR=.; CORE=fceumm; else REPO=libretro/snes9x; REV=fae2fea08f74180759ef540ee94259213f503480; DIR=libretro; CORE=snes9x; fi
  SRC="source-$SYSTEM"
  git init -q "$SRC"
  git -C "$SRC" remote add origin "https://github.com/$REPO.git"
  git -C "$SRC" fetch --depth=1 origin "$REV"
  git -C "$SRC" checkout --detach FETCH_HEAD
  test "$(git -C "$SRC" rev-parse HEAD)" = "$REV"
  if [ -f "$SRC/.gitmodules" ]; then git -C "$SRC" submodule update --init --recursive; fi
  make -C "$SRC/$DIR" -j2 "platform=$1"
  if [ "$1" = win ]; then EXT=dll; else EXT=dylib; fi
  LIB=$(find "$SRC" -type f -name "${CORE}_libretro.$EXT" -print -quit)
  test -n "$LIB"; cp "$LIB" package-cores/
  FOUND=0
  for f in "$SRC"/LICENSE* "$SRC"/COPYING*; do
    if [ -f "$f" ]; then cp "$f" "third-party-notices/$SYSTEM-$(basename "$f")"; FOUND=1; fi
  done
  test "$FOUND" = 1
  printf '%s @ %s\n' "$REPO" "$REV" > "third-party-notices/$SYSTEM-source.txt"
done
if [ "$1" = win ]; then
  for file in libwinpthread-1.dll libgcc_s_seh-1.dll libstdc++-6.dll; do
    if [ -f "/mingw64/bin/$file" ]; then cp "/mingw64/bin/$file" package-cores/; fi
  done
fi
