# ADR-005: Política fail-safe e prioridade de restrições
**Status:** aceita
**Decisão:** sem dado válido, com dado implausível ou com falha de autenticação => ventilação mínima (exaustor nível 1), nunca "desligado". O firmware aplica o mesmo modo após `FAILSAFE_MS` sem comando válido. O teto de CO₂ (1500 ppm) **vence** o limite de ruído noturno e o anti short-cycling (cadeia de guardas: SafeMode → Ceiling → Noise → MinRuntime).
**Consequências:** segurança respiratória acima de conforto acústico; pode acordar o morador em caso extremo, o que fica registrado como evento.
