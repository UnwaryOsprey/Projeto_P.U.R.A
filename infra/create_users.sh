#!/usr/bin/env bash
# Cria infra/mosquitto/passwd com usuários pura-server, esp32-sala e esp32-quarto (senhas aleatórias).
set -euo pipefail
cd "$(dirname "$0")/mosquitto"
rm -f passwd; touch passwd
for u in pura-server esp32-sala esp32-quarto; do
  p="$(openssl rand -hex 8)"
  docker run --rm -v "$PWD:/w" eclipse-mosquitto:2 mosquitto_passwd -b /w/passwd "$u" "$p"
  echo "$u  senha: $p"
done
chmod 644 passwd
echo "Guarde as senhas: servidor -> PURA_MQTT_PASSWORD no .env; nós -> MQTT_PASS no config.h."
