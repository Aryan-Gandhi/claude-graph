#!/bin/bash
# Usage: open.sh <project-slug>
# Copies the page next to the project's state.js and opens it in Chrome once.
set -e
slug="${1:?usage: open.sh <project-slug>}"
src="$(cd "$(dirname "$0")" && pwd)/index.html"
dir="$HOME/.claude/graph/$slug"
mkdir -p "$dir"
cp "$src" "$dir/index.html"
if [ ! -f "$dir/.opened" ] || [ "$2" = "--force" ]; then
  touch "$dir/.opened"
  open -a "Google Chrome" "file://$dir/index.html"
  echo "Opened file://$dir/index.html"
else
  echo "Already open: file://$dir/index.html (page refreshes itself every 2s)"
fi
