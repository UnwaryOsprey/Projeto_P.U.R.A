# Usando ESP32 real (modo MQTT, sem Docker)

O modo local (`python -m pura`) usa nós virtuais. Para ligar um ESP32 de verdade, o servidor passa a falar MQTT com um broker **Mosquitto instalado direto no computador**.

## 1. Instalar o Mosquitto (Windows)

1. Baixe o instalador em <https://mosquitto.org/download/> e instale.
2. O instalador pode registrar o Mosquitto como serviço, ocupando a porta 1883 com a configuração padrão (só aceita conexões locais). Pare o serviço, em um PowerShell **como administrador**:
   ```powershell
   net stop mosquitto
   ```
3. Inicie o broker com a configuração do projeto, em um terminal na pasta do projeto (deixe-o aberto):
   ```powershell
   & "C:\Program Files\mosquitto\mosquitto.exe" -c infra\mosquitto\mosquitto.dev.conf -v
   ```

Linux: `sudo apt install mosquitto` e `mosquitto -c infra/mosquitto/mosquitto.dev.conf -v`. macOS: `brew install mosquitto`.

## 2. Liberar a porta no firewall (PowerShell como administrador)

```powershell
New-NetFirewallRule -DisplayName "PURA MQTT" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
```

Descubra o IP do computador com `ipconfig` (campo "Endereço IPv4"). O ESP32 e o computador precisam estar na mesma rede Wi-Fi.

## 3. Chaves de assinatura

Gere uma chave por cômodo:

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(16))"
```

Coloque no `.env` e use **a mesma chave** no `HMAC_KEY` do firmware daquele cômodo:

```
PURA_KEYS=sala=<chave-da-sala>,quarto=<chave-do-quarto>
PURA_MQTT_HOST=localhost
PURA_MQTT_PORT=1883
```

## 4. Servidor em modo MQTT

```powershell
.venv\Scripts\python -m pip install -e ".[mqtt]"
.venv\Scripts\python -m pura --mqtt --open
```

Para testar o caminho MQTT sem hardware, em outro terminal rode os nós virtuais contra o mesmo broker:

```powershell
.venv\Scripts\python -m pura.simulator
```

## 5. Firmware

Ligações, bibliotecas, `config.h`, checklist de validação e calibração: [`hardware-testing.md`](hardware-testing.md) (seções 1, 3, 4 e 5). No `config.h`, `MQTT_HOST` é o IP do computador (não `localhost`), `MQTT_PORT 1883`, `USE_TLS 0`.

## Problemas comuns

- **`Only one usage of each socket address`** ao iniciar o broker: o serviço do Mosquitto ainda está ativo (`net stop mosquitto`).
- **ESP32 não conecta:** confira o IP em `MQTT_HOST`, a rede Wi-Fi e o firewall (porta 1883).
- **Painel mostra "sem dados" ou eventos `reading_rejected (auth)`:** `PURA_KEYS` diferente do `HMAC_KEY` do firmware.
- **`reading_rejected (skew)`:** relógio do ESP32 fora de hora; confirme que o NTP funcionou (`NTP ok` no serial).
