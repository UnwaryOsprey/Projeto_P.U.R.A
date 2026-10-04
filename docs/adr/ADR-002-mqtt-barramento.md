# ADR-002: MQTT como barramento e payload único assinado por leitura
**Status:** aceita
**Contexto:** ESP32 com Wi-Fi, poucos recursos, redes instáveis.
**Decisão:** MQTT (Mosquitto) com QoS 1 para comandos, Last Will para presença, e **um tópico `sensor` com JSON assinado** (em vez de um tópico por grandeza) para que a leitura seja atômica e verificável com um único HMAC.
**Consequências:** menos mensagens e verificação simples; o payload é um pouco maior (buffer de 512 B no firmware).
