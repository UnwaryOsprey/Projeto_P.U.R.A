/*
 * P.U.R.A. - nó ESP32 (sensores + atuadores)
 * Requer Arduino-ESP32 core 3.x (API ledcAttach) e as bibliotecas:
 *   PubSubClient (Nick O'Leary), ArduinoJson (6.x ou 7.x),
 *   SensirionI2CScd4x (se HAS_SCD4X), Adafruit SGP30 (se HAS_SGP30)
 *
 * Protocolo: docs/protocolo.md
 *   publica  pura/{casa}/{comodo}/sensor        (JSON assinado com HMAC-SHA256)
 *   assina   pura/{casa}/{comodo}/atuador/cmd   (JSON assinado; verifica assinatura, janela de tempo e nonce)
 *   publica  pura/{casa}/{comodo}/atuador/state e .../status (LWT)
 * Fail-safe: sem comando válido por FAILSAFE_MS => exaustor nível 1, purificador 0 (nunca "tudo desligado").
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "mbedtls/md.h"
#include "config.h"

#if HAS_SCD4X
#include <Wire.h>
#include <SensirionI2CScd4x.h>
SensirionI2CScd4x scd4x;
#endif
#if HAS_SGP30
#include <Wire.h>
#include <Adafruit_SGP30.h>
Adafruit_SGP30 sgp;
#endif
#if HAS_PMS5003
HardwareSerial pmsSerial(2);
#endif

#if USE_TLS
WiFiClientSecure net;
#else
WiFiClient net;
#endif
PubSubClient mqtt(net);

char topicSensor[96], topicCmd[96], topicState[96], topicStatus[96], nodeId[48];
uint8_t lvlExhaust = 1, lvlPurifier = 0;  // começa em modo seguro
bool failsafe = true;
uint32_t lastCmdMs = 0, lastPubMs = 0;
String recentNonces[8];
uint8_t nonceIdx = 0;
float co2 = -1, pm25 = -1, voc = -1, temp = -1, hum = -1;  // -1 = sensor ausente

// ---------- criptografia ----------
String hmacHex(const char* key, const char* msg) {
  unsigned char out[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)key, strlen(key));
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)msg, strlen(msg));
  mbedtls_md_hmac_finish(&ctx, out);
  mbedtls_md_free(&ctx);
  static const char* hex = "0123456789abcdef";
  String s;
  for (int i = 0; i < 32; i++) { s += hex[out[i] >> 4]; s += hex[out[i] & 15]; }
  return s;
}

bool constantTimeEq(const String& a, const String& b) {
  if (a.length() != b.length()) return false;
  uint8_t diff = 0;
  for (size_t i = 0; i < a.length(); i++) diff |= a[i] ^ b[i];
  return diff == 0;
}

bool timeValid() { return time(nullptr) > 1700000000; }

// ---------- atuadores ----------
void applyLevels() {
  static const uint8_t duty[4] = {0, 85, 170, 255};
  ledcWrite(PIN_EXHAUST, duty[lvlExhaust]);
  ledcWrite(PIN_PURIFIER, duty[lvlPurifier]);
}

void publishState() {
  char buf[128];
  snprintf(buf, sizeof buf, "{\"exhaust\":%d,\"purifier\":%d,\"failsafe\":%s,\"rssi\":%d}",
           lvlExhaust, lvlPurifier, failsafe ? "true" : "false", WiFi.RSSI());
  mqtt.publish(topicState, buf);
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  StaticJsonDocument<256> d;
  if (deserializeJson(d, payload, len)) { Serial.println("cmd: JSON inválido"); return; }
  uint32_t ts = d["ts"] | 0;
  const char* nonce = d["nonce"] | "";
  int ex = d["exhaust"] | -1, pu = d["purifier"] | -1;
  const char* sig = d["sig"] | "";
  if (ex < 0 || ex > 3 || pu < 0 || pu > 3) { Serial.println("cmd: nível inválido"); return; }

  char msg[128];
  snprintf(msg, sizeof msg, "cmd|%s|%lu|%s|%d|%d", ROOM, (unsigned long)ts, nonce, ex, pu);
  if (!constantTimeEq(hmacHex(HMAC_KEY, msg), String(sig))) { Serial.println("cmd: ASSINATURA INVÁLIDA, descartado"); return; }
  if (timeValid() && labs((long)time(nullptr) - (long)ts) > MAX_SKEW_S) { Serial.println("cmd: fora da janela de tempo"); return; }
  for (auto& n : recentNonces) if (n == nonce) { Serial.println("cmd: replay descartado"); return; }
  recentNonces[nonceIdx++ & 7] = nonce;

  lvlExhaust = ex; lvlPurifier = pu; failsafe = false; lastCmdMs = millis();
  applyLevels();
  Serial.printf("cmd ok: exaustor=%d purificador=%d\n", ex, pu);
  publishState();
}

// ---------- sensores ----------
#if HAS_PMS5003
void readPMS() {
  static uint8_t buf[32];
  static uint8_t idx = 0;
  while (pmsSerial.available()) {
    uint8_t b = pmsSerial.read();
    if (idx == 0 && b != 0x42) continue;
    if (idx == 1 && b != 0x4D) { idx = 0; continue; }
    buf[idx++] = b;
    if (idx == 32) {
      idx = 0;
      uint16_t sum = 0;
      for (int i = 0; i < 30; i++) sum += buf[i];
      if (sum == (uint16_t)((buf[30] << 8) | buf[31])) pm25 = (buf[12] << 8) | buf[13];  // PM2.5 atmosférico
    }
  }
}
#endif

void readSensors() {
#if SIMULATE_SENSORS
  co2 = 600 + 300 * sin(millis() / 60000.0);
  pm25 = 8 + 6 * sin(millis() / 45000.0) + 6;
  voc = 120; temp = 24.5; hum = 55;
#else
 #if HAS_SCD4X
  uint16_t c = 0; float t = 0, h = 0;
  if (!scd4x.readMeasurement(c, t, h) && c != 0) { co2 = c; temp = t; hum = h; }
 #endif
 #if HAS_PMS5003
  readPMS();
 #endif
 #if HAS_SGP30
  if (sgp.IAQmeasure()) voc = sgp.TVOC;
 #endif
#endif
}

void publishReading() {
  if (!timeValid()) { Serial.println("aguardando NTP: leitura não enviada"); return; }
  char nonce[17];
  snprintf(nonce, sizeof nonce, "%08x%08x", (unsigned)esp_random(), (unsigned)esp_random());
  uint32_t ts = time(nullptr);
  char sign[200];
  snprintf(sign, sizeof sign, "%s|%lu|%s|%.1f|%.1f|%.1f|%.1f|%.1f", nodeId, (unsigned long)ts, nonce, co2, pm25, voc, temp, hum);
  String sig = hmacHex(HMAC_KEY, sign);
  char payload[384];
  snprintf(payload, sizeof payload,
           "{\"v\":1,\"node\":\"%s\",\"ts\":%lu,\"nonce\":\"%s\",\"co2\":%.1f,\"pm25\":%.1f,\"voc\":%.1f,\"temp\":%.1f,\"hum\":%.1f,\"sig\":\"%s\"}",
           nodeId, (unsigned long)ts, nonce, co2, pm25, voc, temp, hum, sig.c_str());
  mqtt.publish(topicSensor, payload);
  Serial.printf("pub: CO2=%.0f PM2.5=%.1f VOC=%.0f T=%.1f UR=%.0f\n", co2, pm25, voc, temp, hum);
}

// ---------- conexão ----------
void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf(" ok (%s)\n", WiFi.localIP().toString().c_str());
  configTime(0, 0, "pool.ntp.org", "time.google.com");  // NTP: necessário para o timestamp e para validar TLS
  for (int i = 0; i < 30 && !timeValid(); i++) delay(500);
  Serial.println(timeValid() ? "NTP ok" : "NTP indisponível (leituras só serão enviadas após sincronizar)");
}

void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.print("MQTT...");
    if (mqtt.connect(nodeId, MQTT_USER, MQTT_PASS, topicStatus, 1, true, "offline")) {
      Serial.println(" ok");
      mqtt.publish(topicStatus, "online", true);
      mqtt.subscribe(topicCmd, 1);
      publishState();
    } else {
      Serial.printf(" falhou (rc=%d), tentando de novo\n", mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  snprintf(nodeId, sizeof nodeId, "esp32-%s", ROOM);
  snprintf(topicSensor, sizeof topicSensor, "pura/%s/%s/sensor", HOUSE, ROOM);
  snprintf(topicCmd, sizeof topicCmd, "pura/%s/%s/atuador/cmd", HOUSE, ROOM);
  snprintf(topicState, sizeof topicState, "pura/%s/%s/atuador/state", HOUSE, ROOM);
  snprintf(topicStatus, sizeof topicStatus, "pura/%s/%s/status", HOUSE, ROOM);

  ledcAttach(PIN_EXHAUST, PWM_FREQ_HZ, 8);
  ledcAttach(PIN_PURIFIER, PWM_FREQ_HZ, 8);
  applyLevels();  // modo seguro desde o boot

#if HAS_SCD4X || HAS_SGP30
  Wire.begin();
#endif
#if HAS_SCD4X
  scd4x.begin(Wire);
  scd4x.stopPeriodicMeasurement();
  scd4x.startPeriodicMeasurement();
#endif
#if HAS_SGP30
  if (!sgp.begin()) Serial.println("SGP30 não encontrado");
#endif
#if HAS_PMS5003
  pmsSerial.begin(9600, SERIAL_8N1, 16, 17);
#endif

  connectWifi();
#if USE_TLS
  net.setCACert(CA_CERT);
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setCallback(onMessage);
  lastCmdMs = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) { WiFi.reconnect(); delay(1000); return; }
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();
  static uint32_t lastReadMs = 0;
  if (millis() - lastReadMs >= 1000) { lastReadMs = millis(); readSensors(); }  // sensores atualizam a ~5 s

  if (millis() - lastPubMs >= PUBLISH_PERIOD_MS) {
    lastPubMs = millis();
    publishReading();
  }
  if (!failsafe && millis() - lastCmdMs > FAILSAFE_MS) {
    failsafe = true; lvlExhaust = 1; lvlPurifier = 0;
    applyLevels(); publishState();
    Serial.println("FAIL-SAFE: sem comando válido, ventilação mínima");
  }
}
