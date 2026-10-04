# Política de segurança

## Reportar vulnerabilidades
Abra um *security advisory* privado no GitHub (aba *Security*) ou fale diretamente com os mantenedores. Não publique detalhes em issues públicas antes da correção.

## Escopo e regras para testes
- Testes de ataque (replay, publicação não autorizada, flooding, comandos forjados) **somente no broker e nos dispositivos do próprio grupo**, em laboratório.
- É proibido capturar ou testar tráfego de redes de terceiros.
- Nunca faça commit de chaves HMAC, senhas MQTT, certificados ou `config.h`.

## Limitações conhecidas (MVP)
Chave HMAC gravada no firmware; `atuador/state` sem assinatura; sem OTA assinado; modo dev sem criptografia de transporte. Veja `docs/protocolo.md`.
