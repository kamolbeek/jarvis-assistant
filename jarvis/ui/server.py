"""Orb bilan aloqa uchun lokal WebSocket serveri.

Yadro holat o'zgarishlarini shu server orqali orb'ga uzatadi, orb esa
foydalanuvchi harakatlarini (bosish, tasdiqlash) qaytaradi. Faqat 127.0.0.1
da tinglaydi — tashqaridan ulanib bo'lmaydi.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from ..bus import EventBus, State

log = logging.getLogger("jarvis.ui")

CommandHandler = Callable[[dict[str, Any]], Awaitable[None]]


class UiServer:
    """Orb'ga hodisa uzatuvchi va undan buyruq qabul qiluvchi server."""

    def __init__(self, bus: EventBus, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.bus = bus
        self.host = host
        self.port = port
        self._clients: set[ServerConnection] = set()
        self._server: Any = None
        self._unsubscribe: Callable[[], None] | None = None
        self._handlers: dict[str, CommandHandler] = {}

    def on(self, command: str, handler: CommandHandler) -> None:
        """Orb'dan keladigan buyruqqa ishlov beruvchi qo'shadi."""
        self._handlers[command] = handler

    async def start(self) -> None:
        self._unsubscribe = self.bus.subscribe(self._broadcast)
        self._server = await websockets.serve(self._handle_client, self.host, self.port)
        log.info("UI serveri tinglayapti: ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            log.info("UI serveri to'xtadi")

    # --- Ichki ---

    async def _broadcast(self, event: dict[str, Any]) -> None:
        """Hodisani barcha ulangan orb'larga yuboradi."""
        if not self._clients:
            return
        payload = json.dumps(event, ensure_ascii=False)
        dead: list[ServerConnection] = []
        for client in self._clients:
            try:
                await client.send(payload)
            except websockets.exceptions.ConnectionClosed:
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    async def _handle_client(self, websocket: ServerConnection) -> None:
        self._clients.add(websocket)
        log.info("Orb ulandi (jami %d)", len(self._clients))

        # Yangi ulangan orb darhol joriy holatni bilsin
        try:
            await websocket.send(
                json.dumps({"type": "state", "state": str(self.bus.state)})
            )
        except websockets.exceptions.ConnectionClosed:
            self._clients.discard(websocket)
            return

        try:
            async for raw in websocket:
                await self._handle_message(raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            log.info("Orb uzildi (qoldi %d)", len(self._clients))

    async def _handle_message(self, raw: str | bytes) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Orb'dan noto'g'ri JSON keldi")
            return
        if not isinstance(message, dict):
            return

        command = str(message.get("type", ""))

        # Tasdiq javobi — maxsus, chunki to'g'ridan-to'g'ri shinaga boradi
        if command == "confirm_result":
            confirm_id = str(message.get("id", ""))
            approved = bool(message.get("approved", False))
            if not self.bus.resolve_confirm(confirm_id, approved):
                log.warning("Noma'lum tasdiq ID: %s", confirm_id)
            return

        handler = self._handlers.get(command)
        if handler is None:
            log.debug("Ishlov beruvchi yo'q: %s", command)
            return
        try:
            await handler(message)
        except Exception:
            log.exception("Buyruqni bajarishda xato: %s", command)
            await self.bus.set_state(State.ERROR)
            await asyncio.sleep(1.5)
            await self.bus.set_state(State.IDLE)
