#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
prefix="$HOME/rffp-review-eda/install"
mkdir -p "$HOME/rffp-review-eda"
cd "$HOME/rffp-review-eda"
if [ ! -d magic ]; then
  git clone --depth 1 --branch 8.3.684 https://github.com/RTimothyEdwards/magic.git magic
fi
if [ ! -x "$prefix/bin/magic" ]; then
  (cd magic && ./configure --prefix="$prefix" > "$root/review/magic-build.log" 2>&1 &&
    make -j4 >> "$root/review/magic-build.log" 2>&1 && make install >> "$root/review/magic-build.log" 2>&1)
fi
if [ ! -d netgen ]; then
  git clone --depth 1 --branch 1.5.324 https://github.com/RTimothyEdwards/netgen.git netgen
fi
if [ ! -x "$prefix/bin/netgen" ]; then
  (cd netgen && ./configure --prefix="$prefix" > "$root/review/netgen-build.log" 2>&1 &&
    make -j4 >> "$root/review/netgen-build.log" 2>&1 && make install >> "$root/review/netgen-build.log" 2>&1)
fi
echo "Compatible Magic and Netgen installed in $prefix/bin"
