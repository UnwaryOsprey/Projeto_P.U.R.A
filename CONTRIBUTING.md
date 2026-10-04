# Como contribuir

## Fluxo
1. Abra ou escolha uma *issue* (labels: `bug`, `feature`, `hardware`, `docs`, `good first issue`).
2. Crie uma branch a partir de `main`: `feat/nome-curto`, `fix/...`, `docs/...`.
3. Commits no padrão *conventional commits*: `feat(guards): ...`, `fix(firmware): ...`, `docs: ...`, `test: ...`.
4. Abra um PR usando o template. **Todo PR precisa de revisão de outra pessoa** (ninguém aprova o próprio PR). Proteja a `main` no GitHub (*Settings → Branches*: exigir PR, 1 aprovação e CI verde).
5. Não faça push direto na `main`.

## Ambiente
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && pytest
```

## Regras do projeto
- Mudou função objetivo, restrição ou guarda? Atualize os testes em `tests/` e `docs/modelagem.md`.
- Decisão de arquitetura relevante? Crie um ADR em `docs/adr/` (`ADR-00N-titulo.md`: contexto, decisão, consequências).
- Mudou o protocolo MQTT? Atualize `docs/protocolo.md`, o firmware **e** `security.py` no mesmo PR.
- Resultados de experimentos: sempre ≥ 30 execuções com média e desvio-padrão, contra o baseline; resultados negativos também entram no relatório.
- **Nunca** commite segredos (`.env`, `config.h`, chaves, certificados, senhas). Se vazar, troque a chave imediatamente e avise o grupo.
- Dados sintéticos precisam estar documentados (regra de geração e premissas).

## Bom primeiro PR
Calibrar as tabelas de `dynamics.py` com medições reais; adicionar um sensor ao firmware; melhorar a estimativa de ocupação; novo gráfico no dashboard.
