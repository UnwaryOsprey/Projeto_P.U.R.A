"""API REST + WebSocket + dashboard estático."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..service import PuraService

STATIC = Path(__file__).parent / "static"


class OptimizerBody(BaseModel):
    name: str


def create_app(service: PuraService, autostart: bool = True) -> FastAPI:
    clients: set[WebSocket] = set()
    loop_ref: dict = {}

    async def broadcast():
        data = service.snapshot()
        for ws in list(clients):
            try:
                await ws.send_json(data)
            except Exception:
                clients.discard(ws)

    def on_event(_event):  # chamado de threads do MQTT
        loop = loop_ref.get("loop")
        if loop and clients:
            asyncio.run_coroutine_threadsafe(broadcast(), loop)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop_ref["loop"] = asyncio.get_running_loop()
        service.events.subscribe(on_event)
        if autostart:
            service.start()
        yield
        if autostart:
            service.stop()

    app = FastAPI(title="P.U.R.A.", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "optimizer": service.optimizer_name}

    @app.get("/api/state")
    def state():
        return service.snapshot()

    @app.post("/api/optimizer")
    def set_optimizer(body: OptimizerBody, x_api_token: str | None = Header(default=None)):
        if service.s.api_token and x_api_token != service.s.api_token:
            raise HTTPException(401, "token inválido")
        try:
            service.set_optimizer(body.name)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {"optimizer": service.optimizer_name}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        clients.add(websocket)
        try:
            await websocket.send_json(service.snapshot())
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(websocket)

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
