"""Servidor P.U.R.A.

    python -m pura            modo local: servidor + ESP32 virtuais + painel (sem broker, sem Docker)
    python -m pura --mqtt     modo MQTT: conecta num broker (para ESP32 reais)
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser

import uvicorn

from .adapters.local_bus import LocalBus
from .api.app import create_app
from .config import Settings
from .envfile import load_dotenv
from .service import PuraService

# Valores de demonstração (ciclos curtos). Só valem se o .env/ambiente não definir.
DEMO_DEFAULTS = {
    "PURA_CYCLE_S": "10", "PURA_MIN_RUN_S": "30", "PURA_HEARTBEAT_S": "60", "PURA_STALE_S": "60",
}


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m pura", description="P.U.R.A. - servidor e painel")
    p.add_argument("--mqtt", action="store_true", help="usa um broker MQTT externo (ESP32 reais) em vez do simulador local")
    p.add_argument("--host", default="127.0.0.1", help="endereco do painel (use 0.0.0.0 para abrir na rede local)")
    p.add_argument("--port", type=int, default=None, help="porta do painel (padrao: PURA_API_PORT ou 8000)")
    p.add_argument("--open", action="store_true", help="abre o painel no navegador")
    p.add_argument("--speed", type=float, default=float(os.environ.get("PURA_SIM_SPEED") or 30), help="aceleracao do tempo simulado")
    p.add_argument("--period", type=float, default=float(os.environ.get("PURA_SIM_PERIOD_S") or 2), help="periodo de publicacao das leituras (s)")
    p.add_argument("--seed", type=int, default=int(os.environ.get("PURA_SIM_SEED") or 0), help="semente do cenario simulado")
    return p.parse_args(argv)


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def main(argv=None) -> None:
    env_path = load_dotenv()  # antes do parse_args: os padroes de --speed etc. vem do .env
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.mqtt:
        for k, v in DEMO_DEFAULTS.items():
            if not os.environ.get(k):
                os.environ[k] = v
    s = Settings.from_env()
    if args.port:
        s.api_port = args.port
    if not _port_free(args.host, s.api_port):
        sys.exit(f"A porta {s.api_port} ja esta em uso. Tente: python -m pura --port {s.api_port + 1}")

    sim = None
    if args.mqtt:
        try:
            from .adapters.mqtt_bus import MqttBus
        except ModuleNotFoundError:
            sys.exit('Modo MQTT precisa do paho-mqtt. Instale com:  pip install -e ".[mqtt]"')
        bus = MqttBus(s, client_id="pura-server", username=s.mqtt_user, password=s.mqtt_password,
                      will=(f"pura/{s.house}/server/status", "offline"))
        mode = f"MQTT em {s.mqtt_host}:{s.mqtt_port}"
    else:
        from .local_run import LocalSimulation, ensure_keys
        ensure_keys(s)
        bus = LocalBus()
        sim = LocalSimulation(s, bus, speed=args.speed, period=args.period, seed=args.seed)
        mode = "local (ESP32 virtuais, sem broker)"

    service = PuraService(s, bus)
    app = create_app(service, autostart=False)
    service.start()
    if sim:
        sim.start()

    shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{shown}:{s.api_port}"
    print(f"\n  P.U.R.A. | modo {mode}"
          f"\n  .env: {env_path or 'nao encontrado (usando padroes)'}"
          f"\n  Painel: {url}   (Ctrl+C para parar)\n", flush=True)
    if args.open:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    try:
        uvicorn.run(app, host=args.host, port=s.api_port, log_level="warning")
    finally:
        if sim:
            sim.stop()
        service.stop()


if __name__ == "__main__":
    main()
