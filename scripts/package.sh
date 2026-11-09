#!/usr/bin/env bash
# Package skills as dist/<name>.skill (Claude) and dist/<name>.zip (ChatGPT and other Agent Skills
# platforms) after the shared checks. See scripts/package.py.
# Usage: scripts/package.sh [--dev] [skill-name ...]   (no names = all skills)
set -euo pipefail
exec python3 "$(dirname "$0")/package.py" "$@"
