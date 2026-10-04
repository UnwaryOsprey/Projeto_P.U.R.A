"""Adapter MQTT (paho-mqtt 2.x). O núcleo só conhece a interface subscribe/publish."""
from __future__ import annotations

import logging

import paho.mqtt.client as mqtt

from ..config import Settings
from ..topics import topic_matches

log = logging.getLogger("pura.mqtt")


class MqttBus:
    def __init__(self, settings: Settings, client_id: str, username=None, password=None, will=None):
        self.s = settings
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password)
        if settings.mqtt_ca:
            self.client.tls_set(ca_certs=settings.mqtt_ca)  # valida o broker pela CA do grupo
        if will:
            self.client.will_set(will[0], will[1], qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = lambda c, u, f, rc, p: log.warning("MQTT desconectado: %s", rc)
        self.client.reconnect_delay_set(1, 30)
        self._subs: list = []

    def subscribe(self, topic_filter, callback):
        self._subs.append((topic_filter, callback))
        if self.client.is_connected():
            self.client.subscribe(topic_filter, qos=1)

    def publish(self, topic, payload, qos=1, retain=False):
        self.client.publish(topic, payload, qos=qos, retain=retain)

    def start(self):
        self.client.connect_async(self.s.mqtt_host, self.s.mqtt_port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            log.error("MQTT recusou a conexão: %s", reason_code)
            return
        log.info("MQTT conectado em %s:%s", self.s.mqtt_host, self.s.mqtt_port)
        for filt, _ in self._subs:
            client.subscribe(filt, qos=1)

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        for filt, cb in self._subs:
            if topic_matches(filt, msg.topic):
                try:
                    cb(msg.topic, payload)
                except Exception:
                    log.exception("erro tratando %s", msg.topic)
