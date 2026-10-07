"""Leitor mínimo de arquivo .env (sem dependências).

No Windows não existe `source .env`, então o próprio programa lê o arquivo.
Variáveis já definidas no ambiente têm prioridade sobre o arquivo.
"""
from __future__ import annotations

import os
from pathlib import Path


def parse_env_text(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:  # comentário no fim da linha
            value = value.split(" #", 1)[0].rstrip()
        if key:
            out[key] = value
    return out


def find_env_file() -> Path | None:
    explicit = os.environ.get("PURA_ENV_FILE")
    candidates = [Path(explicit)] if explicit else []
    candidates += [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    return next((p for p in candidates if p.is_file()), None)


def load_dotenv(path: Path | None = None) -> Path | None:
    """Carrega o .env para os.environ. Retorna o caminho usado (ou None)."""
    path = path or find_env_file()
    if path is None:
        return None
    # utf-8-sig: o Bloco de Notas do Windows costuma gravar UTF-8 com BOM
    for k, v in parse_env_text(path.read_text(encoding="utf-8-sig")).items():
        if k not in os.environ:
            os.environ[k] = v
    return path
