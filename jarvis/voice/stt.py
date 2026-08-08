"""Nutqni matnga aylantirish (STT), o'zbek tiliga urg'u bilan.

Provayderlar almashtiriladigan qilib yozilgan, chunki o'zbek tili uchun sifat
provayderdan provayderga sezilarli farq qiladi:

  * elevenlabs   — Scribe modeli, o'zbek tilini qo'llaydi, umumiy sifat yaxshi;
  * mohir        — Mohir.ai / UzbekVoice, aynan o'zbek tiliga o'rgatilgan;
  * whisper_local— internetsiz ishlaydi, Apple Silicon'da MLX orqali tez.

Sifatni o'z ovozingizda o'lchab, birini tanlang: `voice.stt.provider`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from abc import ABC, abstractmethod

import httpx
import numpy as np

from ..config import env, require_env

log = logging.getLogger("jarvis.voice.stt")

# Juda qisqa yozuvni provayderga yubormaymiz — bu deyarli har doim tasodifiy shovqin.
MIN_AUDIO_SEC = 0.35


def to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """`int16` massivni WAV baytlariga o'raydi (fayl yozmasdan)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(audio.astype(np.int16).tobytes())
    return buffer.getvalue()


class SttProvider(ABC):
    """Umumiy interfeys."""

    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Audioni matnga aylantiradi. Hech narsa eshitilmasa, bo'sh satr."""

    async def aclose(self) -> None:
        """Resurslarni bo'shatadi."""


class ElevenLabsStt(SttProvider):
    """ElevenLabs Scribe."""

    URL = "https://api.elevenlabs.io/v1/speech-to-text"

    def __init__(self, language: str = "uz", model: str = "scribe_v1") -> None:
        self._language = language
        self._model = model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        api_key = require_env("ELEVENLABS_API_KEY", "ElevenLabs STT uchun")
        wav = to_wav_bytes(audio, sample_rate)

        response = await self._client.post(
            self.URL,
            headers={"xi-api-key": api_key},
            files={"file": ("audio.wav", wav, "audio/wav")},
            data={
                "model_id": self._model,
                "language_code": self._language,
                # Diarizatsiya kerak emas — bitta gapiruvchi.
                "diarize": "false",
            },
        )
        response.raise_for_status()
        return str(response.json().get("text", "")).strip()

    async def aclose(self) -> None:
        await self._client.aclose()


class MohirStt(SttProvider):
    """Mohir.ai / UzbekVoice — o'zbek tiliga ixtisoslashgan.

    Bazaviy URL `MOHIR_STT_URL` orqali o'zgartiriladi, chunki provayder
    endpoint'ni vaqti-vaqti bilan yangilaydi.
    """

    DEFAULT_URL = "https://uzbekvoice.ai/api/v1/stt"

    def __init__(self, language: str = "uz") -> None:
        self._language = language
        self._url = env("MOHIR_STT_URL", self.DEFAULT_URL)
        self._client = httpx.AsyncClient(timeout=60.0)

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        api_key = require_env("MOHIR_API_KEY", "Mohir.ai STT uchun")
        wav = to_wav_bytes(audio, sample_rate)

        response = await self._client.post(
            self._url,
            headers={"Authorization": api_key},
            files={"file": ("audio.wav", wav, "audio/wav")},
            data={"return_offsets": "false", "run_diarization": "false",
                  "language": self._language, "blocking": "true"},
        )
        response.raise_for_status()
        payload = response.json()
        # Javob shakli provayderda o'zgarib turadi — bir nechta kalitni sinab ko'ramiz.
        for key in ("result", "text", "transcript"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict) and isinstance(value.get("text"), str):
                return value["text"].strip()
        return ""

    async def aclose(self) -> None:
        await self._client.aclose()


class WhisperLocalStt(SttProvider):
    """Lokal Whisper (MLX orqali). Internet kerak emas, lekin birinchi ishga tushish sekin."""

    def __init__(self, model: str = "mlx-community/whisper-large-v3-turbo",
                 language: str = "uz") -> None:
        self._model = model
        self._language = language

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        import mlx_whisper

        # Whisper 16 kHz float32 kutadi.
        samples = audio.astype(np.float32) / 32768.0
        if sample_rate != 16000:
            raise ValueError(f"Lokal Whisper uchun 16 kHz kerak, {sample_rate} Hz berildi")

        def run() -> str:
            result = mlx_whisper.transcribe(
                samples, path_or_hf_repo=self._model, language=self._language
            )
            return str(result.get("text", "")).strip()

        # Model CPU/GPU'ni bloklaydi — event loop'ni band qilmaymiz.
        return await asyncio.to_thread(run)


def build_stt(cfg: dict) -> SttProvider:
    provider = str(cfg.get("provider", "elevenlabs")).lower()
    language = str(cfg.get("language", "uz"))

    if provider == "elevenlabs":
        return ElevenLabsStt(language=language)
    if provider == "mohir":
        return MohirStt(language=language)
    if provider == "whisper_local":
        return WhisperLocalStt(
            model=str(cfg.get("model", "mlx-community/whisper-large-v3-turbo")),
            language=language,
        )
    raise ValueError(f"Noma'lum STT provayderi: {provider}")


async def transcribe_guarded(
    provider: SttProvider, audio: np.ndarray, sample_rate: int
) -> str:
    """Juda qisqa yozuvlarni filtrlaydi va xatoda bo'sh satr qaytaradi."""
    duration = audio.size / sample_rate if sample_rate else 0.0
    if duration < MIN_AUDIO_SEC:
        log.debug("Yozuv juda qisqa (%.2f s), o'tkazib yuborildi", duration)
        return ""

    try:
        return await provider.transcribe(audio, sample_rate)
    except httpx.HTTPStatusError as exc:
        log.error("STT xatosi %s: %s", exc.response.status_code, exc.response.text[:200])
    except Exception:
        log.exception("STT bajarilmadi")
    return ""
