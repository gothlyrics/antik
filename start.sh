#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Не найден Python: $PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
  echo "Модуль venv недоступен. Установите python3-venv." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_DIR/requirements.txt"

if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "Файл .env не найден. Скопируйте .env.example в .env и заполните переменные." >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/data"

exec python -m bot.main
