"""Demonstração de segurança em laboratório: dispara eventos contra o gateway principal
  (padrão http://127.0.0.1:8000) para que o painel HTML reflita em tempo real:
  1) tráfego legítimo aceito; 2) falsificação (assinatura inválida) -> alerta + bloqueio do IP;
  3) replay de mensagem antiga (VULN-001) -> 409 + alerta; 4) análise de tráfego."""
import argparse
import json
import time
import urllib.error
import urllib.request

from pura.security import sign

SECRET = b"segredo-de-demonstracao-16+"


def post(port, body, sig):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/telemetry", data=body,
                                 headers={"X-Signature": sig}, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=3).status
    except urllib.error.HTTPError as exc:
        return exc.code


def msg(boot, seq):
    return json.dumps({"node": "S1", "boot": boot, "seq": seq, "t": 26.0, "h": 52, "ppm": 950}).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000, help="Porta do gateway principal (padrão: 8000)")
    a = ap.parse_args()
    port = a.port

    print(f"== Conectando ao Gateway em http://127.0.0.1:{port} ==")
    print("Certifique-se de que o servidor principal está rodando (`python -m pura.server`) e o painel aberto no navegador.\n")

    print("== 1) Tráfego legítimo do ESP32 (boot=111)")
    first = msg(111, 1)
    print("   seq=1 ->", post(port, first, sign(SECRET, first)))
    second = msg(111, 2)
    print("   seq=2 ->", post(port, second, sign(SECRET, second)))
    time.sleep(1)

    print("== 2) O ESP32 reinicia (boot=222) e continua enviando")
    third = msg(222, 1)
    print("   boot=222 seq=1 ->", post(port, third, sign(SECRET, third)))
    time.sleep(1)

    print("== 3) Atacante reenvia mensagem capturada do boot antigo (VULN-001)")
    print("   replay (boot=111, seq=2) ->", post(port, second, sign(SECRET, second)), "(409 = rejeitado)")
    time.sleep(1)

    print("== 4) Falsificação: 6 mensagens com assinatura inválida (aciona o bloqueio de IP)")
    codes = [post(port, msg(999, i), "00" * 32) for i in range(6)]
    print("   códigos:", codes, "(401 ... depois 429 = IP bloqueado)")
    print("   mensagem legítima durante o bloqueio ->", post(port, msg(222, 2), sign(SECRET, msg(222, 2))))

    print("\n== Simulação Concluída! Verifique os contadores e alertas atualizados no painel HTML. ==")


if __name__ == "__main__":
    main()
