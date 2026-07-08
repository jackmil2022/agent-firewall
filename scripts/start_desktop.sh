#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../desktop"
if [ ! -x node_modules/.bin/electron ]; then
  npm install
fi
if node_modules/.bin/electron --version >/dev/null 2>&1; then
  node_modules/.bin/electron .
  exit $?
fi

ROOT="$(cd .. && pwd)"
RUNNER="$ROOT/.electron-runner"
mkdir -p "$RUNNER"
if [ ! -f "$RUNNER/package.json" ]; then
  printf '{"private":true,"devDependencies":{}}\n' > "$RUNNER/package.json"
fi
if [ ! -x "$RUNNER/node_modules/.bin/electron" ]; then
  ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}" npm install electron@33.4.11 --save-dev --prefix "$RUNNER"
fi
"$RUNNER/node_modules/.bin/electron" .
