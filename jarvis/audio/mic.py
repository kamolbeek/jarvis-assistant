"""Mikrofon oqimi: uzluksiz 16 kHz mono audio + oldingi soniyalarni saqlovchi bufer."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

log = logging.getLogger("jarvis.audio.mic")


class MicStream:
    """Mikrofondan kadr-kadr `int16` audio beradi.

    `sounddevice` alohida oqimda (thread) ishlaydi, shuning uchun kadrlarni
    event loop'ga `call_soon_threadsafe` orqali uzatamiz.

    Preroll buferi uyg'otuvchi so'zdan *oldingi* audioni saqlaydi — foydalanuvchi
    "Hey Jarvis, ob-havo qanday?" deb bir nafasda aytsa, savol qismi yo'qolmaydi.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_samples: int = 320,
        device: Any = None,
        preroll_ms: int = 300,
        queue_max: int = 100,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.device = device
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=queue_max)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: Any = None
        self._dropped = 0

        frame_ms = frame_samples * 1000 // sample_rate
        preroll_frames = max(1, preroll_ms // max(1, frame_ms))
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_frames)

    # --- Hayot sikli ---

    async def start(self) -> None:
        import sounddevice as sd

        self._loop = asyncio.get_running_loop()

        def callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
            if status:
                log.debug("Audio oqimi holati: %s", status)
            frame = indata[:, 0].copy()
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._push, frame)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.frame_samples,
            channels=1,
            dtype="int16",
            device=self.device,
            callback=callback,
        )
        self._stream.start()
        log.info("Mikrofon ochildi: %d Hz, %d namunali kadr", self.sample_rate, self.frame_samples)

    def _push(self, frame: np.ndarray) -> None:
        self._preroll.append(frame)
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Yadro band — eng eskisini tashlab, yangisini qo'yamiz.
            self._dropped += 1
            if self._dropped % 50 == 1:
                log.warning("Audio navbati to'ldi, kadrlar tashlanmoqda (%d)", self._dropped)
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(frame)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    async def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            log.info("Mikrofon yopildi")

    async def __aenter__(self) -> MicStream:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.stop()

    # --- O'qish ---

    async def frames(self) -> AsyncIterator[np.ndarray]:
        """Kadrlarni cheksiz oqim sifatida beradi."""
        while True:
            yield await self._queue.get()

    def take_preroll(self) -> np.ndarray:
        """Uyg'otishdan oldingi saqlangan audioni qaytaradi va buferni tozalaydi."""
        if not self._preroll:
            return np.zeros(0, dtype=np.int16)
        chunk = np.concatenate(list(self._preroll))
        self._preroll.clear()
        return chunk

    def drain(self) -> None:
        """Navbatdagi eski kadrlarni tashlaydi — Jarvis gapirib bo'lgach kerak bo'ladi."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


def frame_level(frame: np.ndarray) -> float:
    """Kadrning normallashtirilgan RMS darajasi (0..1) — animatsiya uchun."""
    if frame.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(frame.astype(np.float32)))))
    return min(1.0, rms / 8000.0)
