#!/usr/bin/env bash
# Gera CA + certificado do broker (uso em laboratório).  Uso: ./infra/gen_certs.sh <IP-do-servidor>
set -euo pipefail
IP="${1:?informe o IP do computador que roda o broker, ex.: 192.168.0.10}"
D="$(dirname "$0")/mosquitto/certs"; mkdir -p "$D"; cd "$D"
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365 -subj "/CN=PURA-Lab-CA" -out ca.crt
openssl genrsa -out server.key 2048
openssl req -new -key server.key -subj "/CN=$IP" -out server.csr
printf "subjectAltName=IP:%s,IP:127.0.0.1,DNS:localhost,DNS:mosquitto\n" "$IP" > san.ext
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile san.ext
chmod 644 server.key   # o container do Mosquitto precisa ler (aceitável só em laboratório)
rm -f server.csr san.ext ca.srl
echo "OK. Cole $D/ca.crt no firmware (CA_CERT). Mantenha ca.key fora do repositório."
