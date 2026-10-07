#!/usr/bin/env bash
# P.U.R.A. - inicia tudo em modo local (sem Docker). Uso: ./iniciar.sh [opcoes de python -m pura]
set -euo pipefail
cd "$(dirname "$0")"

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Python 3.10+ nao encontrado."; exit 1; }

[ -x .venv/bin/python ] || { echo "Criando ambiente virtual..."; "$PY" -m venv .venv; }
if [ ! -f .venv/.instalado ]; then
  echo "Instalando dependencias (so na primeira vez)..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e .
  touch .venv/.instalado
fi
[ -f .env ] || cp .env.example .env
exec .venv/bin/python -m pura --open "$@"
