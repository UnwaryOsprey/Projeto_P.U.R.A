# Protocolo MQTT e modelo de ameaças

## Tópicos (`{casa}` = `PURA_HOUSE`, `{comodo}` = nome em `PURA_ROOMS`)

| Tópico | Quem publica | Conteúdo |
|---|---|---|
| `pura/{casa}/{comodo}/sensor` | ESP32 | leitura assinada (JSON) |
| `pura/{casa}/{comodo}/atuador/cmd` | servidor | comando assinado (JSON), QoS 1 |
| `pura/{casa}/{comodo}/atuador/state` | ESP32 | `{"exhaust":n,"purifier":n,"failsafe":bool,"rssi":n}` (informativo, não assinado) |
| `pura/{casa}/{comodo}/status` | ESP32 | `online` / `offline` (retained; `offline` via Last Will) |
| `pura/{casa}/server/status` | servidor | `offline` via Last Will |

## Leitura (`.../sensor`)

```json
{"v":1,"node":"esp32-sala","ts":1790000000,"nonce":"a1b2c3d4e5f6a7b8",
 "co2":612.3,"pm25":8.0,"voc":120.0,"temp":24.1,"hum":55.0,"sig":"<hex>"}
```

- `sig = HMAC-SHA256(chave_do_comodo, "node|ts|nonce|co2|pm25|voc|temp|hum")`, com cada número formatado em `%.1f`.
- Sensor ausente: enviar `-1.0` (o servidor converte para "sem dado").
- O servidor descarta, nesta ordem: JSON inválido (`malformed`) → node diferente do tópico ou assinatura inválida (`auth`) → `ts` fora de ±120 s (`stale`) → nonce repetido (`replay`) → valor fora da faixa física (`implausible`).
- Cada descarte vira o evento `reading_rejected` (aparece no painel).

## Comando (`.../atuador/cmd`)

```json
{"v":1,"ts":1790000000,"nonce":"...","exhaust":2,"purifier":1,"sig":"<hex>"}
```

`sig = HMAC-SHA256(chave_do_comodo, "cmd|{comodo}|ts|nonce|exhaust|purifier")`. O ESP32 verifica assinatura, janela de tempo e nonce. O servidor reenvia o comando vigente a cada `PURA_HEARTBEAT_S` (60 s); se o nó ficar `FAILSAFE_MS` sem comando válido, vai para o modo seguro.

## Níveis de atuação

0 = desligado; 1, 2, 3 = PWM de 33 %, 66 % e 100 %.

## Modelo de ameaças (STRIDE resumido)

| Ameaça | Contramedida implementada | Como testar (só no broker do grupo) |
|---|---|---|
| Sniffing / MITM | TLS 1.2+ no Mosquitto (modo seguro) | `tcpdump` no modo dev vs. seguro |
| Dispositivo falso | usuário/senha por nó + ACL por tópico + HMAC por cômodo | publicar em `sensor` com outro usuário: ACL nega |
| Replay | timestamp + nonce + HMAC | reenviar mensagem capturada: evento `replay` |
| Falsificação de leitura (esconder CO₂ alto) | HMAC; faixa física; salto máximo de 2000 ppm | alterar `co2` no JSON: evento `auth` |
| Comando falso (desligar a ventilação) | HMAC do comando + guarda de nonce no firmware | publicar `cmd` sem assinatura: serial mostra "ASSINATURA INVÁLIDA" |
| DoS / flooding | `message_size_limit`, `max_connections`; watchdog (`stale_s`) | flood no broker de laboratório: servidor segue em modo seguro |
| Perda do servidor/broker | Last Will + fail-safe no firmware | derrubar o broker: exaustor vai a nível 1 após 5 min |

**Limitações conhecidas:** a chave HMAC fica gravada no firmware (sem *secure element*); o `atuador/state` não é assinado; sem OTA assinado no MVP; o modo dev não tem criptografia de transporte.

**Princípio fail-safe:** sem dados válidos, dado implausível ou falha de autenticação ⇒ ventilação mínima garantida, nunca "desligado".
