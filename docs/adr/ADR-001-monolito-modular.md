# ADR-001: Monólito modular em vez de microsserviços
**Status:** aceita
**Contexto:** 9 semanas, 4 integrantes, um servidor local. O enunciado não exige microsserviços.
**Decisão:** um processo Python com módulos de responsabilidade única (`adapters`, `pipeline`, `optimizers`, `guards`, `events`, `api`); só o núcleo conhece o domínio, só os adapters conhecem MQTT.
**Consequências:** deploy simples (Docker Compose), testes rápidos sem broker (`LocalBus`); escalar para várias casas exigiria separar o serviço.
