"""Servidor P.U.R.A.:  python -m pura"""
from __future__ import annotations

import logging

import uvicorn

from .adapters.mqtt_bus import MqttBus
from .api.app import create_app
from .config import Settings
from .service import PuraService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = Settings.from_env()
    bus = MqttBus(s, client_id="pura-server", username=s.mqtt_user, password=s.mqtt_password,
                  will=(f"pura/{s.house}/server/status", "offline"))
    service = PuraService(s, bus)
    uvicorn.run(create_app(service), host=s.api_host, port=s.api_port, log_level="info")


if __name__ == "__main__":
    main()
