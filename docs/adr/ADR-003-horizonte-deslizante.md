# ADR-003: Horizonte deslizante (MPC) para GA/SA
**Status:** aceita
**Contexto:** a ocupação e a geração de poluentes mudam; um plano de 24 h feito de uma vez fica obsoleto.
**Decisão:** a cada ciclo, GA/SA otimizam `horizon_slots` (16 slots = 4 h, em `config.py`) a partir do estado atual e a geração estimada pelo previsor; só o primeiro slot é aplicado. Os baselines e o fuzzy decidem por reação instantânea. O benchmark offline usa o horizonte completo de 24 h.
**Consequências:** custo de ~0,3 s por decisão (cabe folgado no ciclo de 15 min); depende da qualidade da estimativa de geração.
