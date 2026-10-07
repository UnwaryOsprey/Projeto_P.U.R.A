// Copie para config.h (ignorado pelo git) e preencha. NUNCA faça commit do config.h.
#pragma once

// ---- Rede ----
#define WIFI_SSID   "sua-rede"
#define WIFI_PASS   "sua-senha"

// ---- Broker MQTT (IP do computador que roda o broker Mosquitto) ----
#define MQTT_HOST   "192.168.0.10"
#define MQTT_PORT   1883            // 8883 no modo seguro (TLS)
#define MQTT_USER   ""              // modo seguro: "esp32-sala"
#define MQTT_PASS   ""
#define USE_TLS     0               // 1 = TLS validando o certificado da CA do grupo
// Conteúdo de infra/mosquitto/certs/ca.crt (só se USE_TLS = 1)
static const char CA_CERT[] = R"PEM(
-----BEGIN CERTIFICATE-----
...cole aqui o ca.crt...
-----END CERTIFICATE-----
)PEM";

// ---- Identidade do nó (tem de bater com PURA_HOUSE / PURA_ROOMS / PURA_KEYS do servidor) ----
#define HOUSE       "casa1"
#define ROOM        "sala"
#define HMAC_KEY    "TROQUE_ESTA_CHAVE_SALA"

// ---- Sensores presentes (0 = ausente: o nó envia -1 e o servidor ignora o campo) ----
#define SIMULATE_SENSORS 0          // 1 = valores falsos, para testar rede/atuadores sem sensores
#define HAS_SCD4X   1               // CO2/temp/umidade, I2C (SDA=21, SCL=22)
#define HAS_PMS5003 1               // PM2.5, UART2 (RX=16 <- TX do sensor, TX=17)
#define HAS_SGP30   0               // VOC (TVOC ppb), I2C

// ---- Atuadores (PWM). Use MOSFET + fonte separada; NUNCA ligue rede elétrica direto ----
#define PIN_EXHAUST   25
#define PIN_PURIFIER  26
#define PWM_FREQ_HZ   25000

// ---- Temporização ----
#define PUBLISH_PERIOD_MS 5000
#define FAILSAFE_MS       300000    // sem comando válido por 5 min => exaustor nível 1
#define MAX_SKEW_S        120
