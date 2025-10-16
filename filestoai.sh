#!/bin/bash
# FilesToAI Shell Wrapper
# This allows you to run filestoai without installing as a package

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/cli.py" "$@"

