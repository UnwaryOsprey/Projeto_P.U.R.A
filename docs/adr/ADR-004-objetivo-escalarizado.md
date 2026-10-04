# ADR-004: Função objetivo escalarizada, Pareto como extensão
**Status:** aceita
**Contexto:** o objetivo tem exposição, energia, perda térmica e ruído.
**Decisão:** soma ponderada com pesos explícitos (`Weights`) e restrições por penalidade, com métricas reportadas separadamente. NSGA-II fica como extensão se houver tempo.
**Consequências:** comparação direta e simples contra os baselines; os pesos precisam de análise de sensibilidade.
