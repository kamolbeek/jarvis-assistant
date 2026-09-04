"""Orb va telefon bilan aloqa uchun lokal server.

Bitta portda ikki narsa xizmat qiladi:

  * **WebSocket** — orb (Electron) va telefon uchun hodisa/buyruq kanali;
  * **HTTP**      — telefon uchun mobil sahifa (`/`).

Telefonda «Hey Jarvis» deb fon rejimida uyg'otib bo'lmaydi — Apple bunga ruxsat
bermaydi. Shuning uchun telefon uchun bosib-gapirish (push-to-talk) sahifasi
beriladi: sahifani ochasiz, orbni bosasiz, gapirasiz.

Audio ikki tomonga ham **xom PCM** ko'rinishida, base64 bilan uzatiladi.
Shu tanlov tufayli na serverda, na telefonda mp3/opus dekoderi kerak emas.
"""

from __future__ import annotations

import base64
import hmac
import http
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
import websockets
from websockets.asyncio.server import ServerConnection
from websockets.datastructures import Headers
from websockets.http11 import Response

from ..bus import EventBus, State

log = logging.getLogger("jarvis.ui")

CommandHandler = Callable[[dict[str, Any]], Awaitable[None]]

PHONE_PAGE = Path(__file__).resolve().parent.parent.parent / "ui" / "renderer" / "phone.html"

# Telefondan keladigan bitta yozuv uchun yuqori chegara (~60 s @ 16 kHz).
MAX_AUDIO_BYTES = 2_000_000


def pcm_to_base64(audio: np.ndarray) -> str:
    return base64.b64encode(audio.astype(np.int16).tobytes()).decode("ascii")


def base64_to_pcm(data: str) -> np.ndarray:
    raw = base64.b64decode(data)
    usable = len(raw) - (len(raw) % 2)
    return np.frombuffer(raw[:usable], dtype=np.int16)


class UiServer:
    """Orb va telefonga hodisa uzatuvchi, ulardan buyruq qabul qiluvchi server."""

    def __init__(
        self, bus: EventBus, host: str = "127.0.0.1", port: int = 8765, token: str = ""
    ) -> None:
        self.bus = bus
        self.host = host
        self.port = port
        self.token = token
        self._clients: dict[str, ServerConnection] = {}
        self._server: Any = None
        self._unsubscribe: Callable[[], None] | None = None
        self._handlers: dict[str, CommandHandler] = {}

        # Faqat lokal manzilda tinglash himoyaning o'zi. Tarmoqqa ochilganda esa
        # WiFi'dagi har kim kompyuterni boshqara olardi — token majburiy.
        if not self._is_loopback(host) and not token:
            raise RuntimeError(
                f"`ui.host` = {host} — server tarmoqqa ochilmoqda, lekin `ui.token` "
                f"bo'sh. Tokensiz bir tarmoqdagi har qanday qurilma Jarvis orqali "
                f"kompyuteringizni boshqara oladi. config/jarvis.yaml da token qo'ying "
                f"(masalan: openssl rand -hex 16)."
            )

    @staticmethod
    def _is_loopback(host: str) -> bool:
        return host in ("127.0.0.1", "localhost", "::1")

    def _token_ok(self, path: str) -> bool:
        """So'rov yo'lidagi `?t=` token to'g'rimi?"""
        if not self.token:
            return True
        query = parse_qs(urlparse(path).query)
        supplied = query.get("t", [""])[0]
        # Vaqt bo'yicha barqaror solishtirish — token uzunligini o'lchash orqali
        # sekin-asta topib olishning oldini oladi.
        return hmac.compare_digest(supplied, self.token)

    def phone_url(self) -> str:
        """Telefonda ochish uchun manzil."""
        suffix = f"?t={self.token}" if self.token else ""
        return f"http://{self.host}:{self.port}/{suffix}"

    def on(self, command: str, handler: CommandHandler) -> None:
        """Buyruqqa ishlov beruvchi qo'shadi. Xabar ichida `_client` — jo'natuvchi ID'si."""
        self._handlers[command] = handler

    async def start(self) -> None:
        self._unsubscribe = self.bus.subscribe(self._broadcast)
        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            process_request=self._serve_http,
            # Telefondan keladigan audio standart chegaradan kattaroq bo'lishi mumkin.
            max_size=MAX_AUDIO_BYTES + 100_000,
        )
        log.info("UI serveri tinglayapti: http://%s:%d (ws va telefon sahifasi)",
                 self.host, self.port)

    async def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            log.info("UI serveri to'xtadi")

    # --- HTTP: telefon sahifasi ---

    def _serve_http(self, connection: ServerConnection, request: Any) -> Response | None:
        """WebSocket bo'lmagan so'rovlarga javob beradi.

        `None` qaytarilsa, websockets odatdagi WS qo'l berishini davom ettiradi.
        """
        if not self._token_ok(request.path):
            body = b"Token noto'g'ri"
            return Response(
                http.HTTPStatus.UNAUTHORIZED, "Unauthorized",
                Headers([
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ]),
                body,
            )

        # Upgrade sarlavhasi bor bo'lsa — bu WebSocket, aralashmaymiz.
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        path = request.path.split("?")[0]
        if path in ("/", "/index.html", "/phone", "/phone.html"):
            try:
                body = PHONE_PAGE.read_bytes()
            except OSError:
                log.exception("Telefon sahifasi o'qilmadi: %s", PHONE_PAGE)
                return Response(
                    http.HTTPStatus.INTERNAL_SERVER_ERROR, "Server Error",
                    Headers([("Content-Type", "text/plain; charset=utf-8")]),
                    "Telefon sahifasi topilmadi".encode(),
                )
            return Response(
                http.HTTPStatus.OK, "OK",
                Headers([
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ]),
                body,
            )

        message = b"Not Found"
        return Response(
            http.HTTPStatus.NOT_FOUND, "Not Found",
            Headers([
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(message))),
            ]),
            message,
        )

    # --- WebSocket ---

    async def _broadcast(self, event: dict[str, Any]) -> None:
        """Hodisani barcha ulangan mijozlarga yuboradi."""
        if not self._clients:
            return
        payload = json.dumps(event, ensure_ascii=False)
        for client_id, connection in list(self._clients.items()):
            try:
                await connection.send(payload)
            except websockets.exceptions.ConnectionClosed:
                self._clients.pop(client_id, None)

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        """Bitta mijozga xabar yuboradi (telefon javobini o'shanga qaytarish uchun)."""
        connection = self._clients.get(client_id)
        if connection is None:
            return False
        try:
            await connection.send(json.dumps(message, ensure_ascii=False))
            return True
        except websockets.exceptions.ConnectionClosed:
            self._clients.pop(client_id, None)
            return False

    async def send_audio(self, client_id: str, audio: np.ndarray, sample_rate: int) -> bool:
        """Javob ovozini mijozga xom PCM sifatida yuboradi."""
        return await self.send_to(client_id, {
            "type": "reply_audio",
            "pcm": pcm_to_base64(audio),
            "sample_rate": sample_rate,
        })

    async def _handle_client(self, websocket: ServerConnection) -> None:
        # `process_request` HTTP so'rovlarni tekshiradi, lekin WebSocket
        # qo'l berishini o'tkazib yuboradi — shuning uchun tokenni bu yerda
        # ham tekshiramiz.
        if not self._token_ok(websocket.request.path):
            log.warning("Token noto'g'ri — ulanish rad etildi")
            await websocket.close(code=4401, reason="unauthorized")
            return

        client_id = uuid.uuid4().hex[:8]
        self._clients[client_id] = websocket
        log.info("Mijoz ulandi: %s (jami %d)", client_id, len(self._clients))

        try:
            await websocket.send(json.dumps({
                "type": "hello", "client": client_id, "state": str(self.bus.state),
                "standby": self.bus.standby_on,
            }))
        except websockets.exceptions.ConnectionClosed:
            self._clients.pop(client_id, None)
            return

        try:
            async for raw in websocket:
                await self._handle_message(raw, client_id)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.pop(client_id, None)
            log.info("Mijoz uzildi: %s (qoldi %d)", client_id, len(self._clients))

    async def _handle_message(self, raw: str | bytes, client_id: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Mijozdan noto'g'ri JSON keldi")
            return
        if not isinstance(message, dict):
            return

        message["_client"] = client_id
        command = str(message.get("type", ""))

        # Tasdiq javobi to'g'ridan-to'g'ri shinaga boradi.
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
            await self.bus.log_line("Buyruq bajarilmadi", level="error")
            await self.bus.set_state(State.IDLE)
