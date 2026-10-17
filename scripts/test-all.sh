#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${HANDOFFGUARD_TEST_PYTHON:-python3}"

if [[ -z "${HANDOFFGUARD_TEST_PYTHON:-}" ]]; then
  if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
    PYTHON="$ROOT/backend/.venv/bin/python"
  elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  fi
fi

echo "=== Backend: pytest ==="
(cd "$ROOT/backend" && "$PYTHON" -m pytest -q)

echo "=== Frontend: Vitest ==="
(cd "$ROOT/frontend" && npm test)

echo "=== Frontend: production build ==="
(cd "$ROOT/frontend" && npm run build)

echo "PASS: all checks completed successfully."
