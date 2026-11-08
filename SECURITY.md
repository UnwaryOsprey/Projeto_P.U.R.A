# Política de segurança

**Escopo**: código deste repositório (simulador, gateway, firmware). Não há dados reais de terceiros.
**Como reportar**: abra um *security advisory* privado no GitHub ou envie e-mail ao mantenedor (preencher).
**Histórico**: vulnerabilidades já tratadas estão em `docs/VULNERABILIDADES.md` (VULN-001 a VULN-007).
**Limitações conhecidas**: HMAC garante integridade e autenticidade; a confidencialidade depende de TLS (nuvem e firmware
`https://`). Em laboratório com HTTP, use somente rede isolada. O contador anti-replay de comandos fica em RAM no ESP32; telemetria e alertas ficam em RAM no gateway;
o segredo HMAC é compartilhado por todos os nós; o bloqueio é por IP.
**Segredos**: `PURA_SECRET` (16+ caracteres) é obrigatório e nunca vai para o Git.
**Ética**: ataques de teste somente contra o gateway do próprio grupo (`tools/security_demo.py` só fala com 127.0.0.1).
