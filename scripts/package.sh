#!/usr/bin/env bash
# Package skills as .skill files (zip with the skill folder at its root) into dist/.
# Usage: scripts/package.sh [skill-name ...]   (no arguments = all skills)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
dirs=$(find . -path ./dist -prune -o -name SKILL.md -print | xargs -n1 dirname | sort)
for d in $dirs; do
  name=$(basename "$d")
  if [ $# -gt 0 ] && [[ ! " $* " == *" $name "* ]]; then continue; fi
  head -1 "$d/SKILL.md" | grep -q '^---$' || { echo "error: $d/SKILL.md must start with frontmatter" >&2; exit 1; }
  version=$(grep -oE 'Skill version: [0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+' "$d/SKILL.md" | head -1 | cut -d' ' -f3 || true)
  rm -f "dist/$name.skill"
  (cd "$(dirname "$d")" && zip -qr "$OLDPWD/dist/$name.skill" "$name" -x '*.DS_Store' '*__pycache__*')
  echo "dist/$name.skill  ${version:-no version}"
done
