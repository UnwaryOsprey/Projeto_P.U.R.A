# Guia de testes de bancada (quem está com o ESP32)

> ⚠️ Segurança elétrica: ligue ventoinhas DC (ex.: PC fan 12 V PWM) por **MOSFET** (IRLZ44N ou módulo equivalente) com fonte própria e GND comum com o ESP32. **Não conecte rede elétrica (127/220 V) ao protótipo.**

## 1. Ligações

| Componente | Pino do ESP32 | Observação |
|---|---|---|
| SCD40/SCD41 (CO₂, temp, UR) | SDA 21, SCL 22, 3V3, GND | I²C, endereço 0x62 |
| PMS5003 (PM2.5) | RX 16 ← TX do sensor, 5V, GND | UART2 a 9600 baud |
| SGP30 (VOC, opcional) | SDA 21, SCL 22 | compartilha o barramento I²C |
| Exaustor (PWM) | GPIO 25 → gate do MOSFET | 25 kHz |
| Purificador (PWM) | GPIO 26 → gate do MOSFET | 25 kHz |

Sem algum sensor? Ponha `HAS_x 0` no `config.h` (o nó envia `-1` e o servidor ignora o campo). Sem nenhum sensor? Use `SIMULATE_SENSORS 1`.

## 2. Servidor (um integrante, no computador da bancada)

Instale o Mosquitto, libere a porta 1883 e inicie o servidor em modo MQTT: passo a passo em [`esp32-real.md`](esp32-real.md).

```bash
python -m pura --mqtt --open     # painel em http://localhost:8000
```

## 3. Firmware
1. Arduino IDE ≥ 2 com **esp32 by Espressif core 3.x**; instale PubSubClient, ArduinoJson, SensirionI2CScd4x (e Adafruit SGP30 se usar).
2. `cp firmware/esp32/pura_node/config.example.h firmware/esp32/pura_node/config.h` e preencha Wi-Fi, `MQTT_HOST` (IP do servidor), `ROOM`, `HMAC_KEY` (igual a `PURA_KEYS` do servidor para aquele cômodo).
3. Placa "ESP32 Dev Module", gravar, abrir o Monitor Serial a 115200.

## 4. Checklist de validação (registre prints/logs no PR ou issue)

- [ ] Serial mostra `WiFi ok`, `NTP ok`, `MQTT ok` e `pub: CO2=...` a cada 5 s.
- [ ] Dashboard mostra o cômodo "ao vivo" com os valores dos sensores.
- [ ] **CO₂:** respirar perto do SCD4x por 30 s → CO₂ sobe; o nível do exaustor sobe no painel e o serial mostra `cmd ok`. Medir o ventilador reagindo (PWM no osciloscópio/multímetro ou rotação).
- [ ] **PM2.5:** soprar fumaça de incenso/vela apagada perto do PMS5003 → PM2.5 sobe → purificador reage.
- [ ] **Comparação de estratégias:** no seletor do painel, alternar `fuzzy`, `hysteresis`, `ga`; anotar tempo de resposta e comportamento.
- [ ] **Fail-safe do nó:** parar o servidor (`Ctrl+C` no terminal do `python -m pura --mqtt`) → após 5 min o serial mostra `FAIL-SAFE` e o exaustor vai a nível 1.
- [ ] **Sensor offline:** desligar o sensor/nó → após `PURA_STALE_S` o painel mostra "sem dados" e o servidor manda modo seguro.
- [ ] **Segurança (apenas no broker do grupo):** (a) `mosquitto_pub` em `.../sensor` sem assinatura → evento `reading_rejected (auth)`; (b) reenviar uma leitura capturada → `replay`; (c) `mosquitto_pub` em `.../atuador/cmd` sem assinatura → serial `ASSINATURA INVÁLIDA`.
- [ ] Medir latência sensor→comando (timestamp do serial vs. log do servidor) em ≥ 30 amostras e registrar média e p95.

## 5. Calibração
Com o ar externo (~420 ppm) por 10 min, compare com o SCD4x e ajuste `Calibrator` (`src/pura/pipeline.py`) se houver offset. Meça a vazão real do exaustor e o ruído (app de decibelímetro) e atualize as tabelas em `src/pura/model/dynamics.py`: isso melhora a previsão do otimizador.

## 6. Modo seguro (TLS + senha + ACL)
Não incluído nesta versão sem Docker. O Mosquitto nativo suporta `password_file`, `acl_file` e `cafile`/`certfile`/`keyfile`; consulte a documentação do Mosquitto. Até lá, use o broker apenas em rede de laboratório isolada (o HMAC das mensagens continua ativo).
