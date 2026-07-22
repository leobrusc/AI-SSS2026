#!/bin/bash
# Import a campaign bundle into the repository
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <bundle.tar.gz>"
    exit 1
fi

BUNDLE="$1"
if [ ! -f "$BUNDLE" ]; then
    echo "Error: Bundle file not found: $BUNDLE"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Importing bundle: $BUNDLE"
echo "Target: $PROJECT_ROOT"

tar -xzf "$BUNDLE" -C "$PROJECT_ROOT"
echo "Import complete."
