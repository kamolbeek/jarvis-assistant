"""Nutqni matnga aylantirish (STT), o'zbek tiliga urg'u bilan.

Provayderlar almashtiriladigan qilib yozilgan, chunki o'zbek tili uchun sifat
provayderdan provayderga sezilarli farq qiladi:

  * elevenlabs   — Scribe modeli, o'zbek tilini qo'llaydi, umumiy sifat yaxshi;
  * mohir        — Mohir.ai / UzbekVoice, aynan o'zbek tiliga o'rgatilgan;
  * whisper_local— internetsiz ishlaydi, Apple Silicon'da MLX orqali tez;
  * whisper_cpp  — internetsiz, whisper.cpp orqali GGML modeli. Aynan shu yo'l
                   bilan o'zbekchaga o'rgatilgan **rubaiSTT** modelini ulash
                   mumkin (RubaiSTT Dictation ilovasi ham shu modelni shu
                   dvigatel bilan ishlatadi).

Sifatni o'z ovozingizda o'lchab, birini tanlang: `voice.stt.provider`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import shutil
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path

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


class WhisperCppStt(SttProvider):
    """whisper.cpp orqali lokal GGML modeli — internetsiz, kalitsiz, bepul.

    Asosiy foydasi: o'zbek tiliga aynan o'rgatilgan **rubaiSTT** modelini
    ishlatish mumkin. RubaiSTT Dictation ilovasi ham xuddi shu modelni xuddi
    shu dvigatel bilan yuritadi — ya'ni ilovani "boshqarish" shart emas,
    modelning o'ziga murojaat qilamiz va sifat bir xil bo'ladi.

    Model ham, buyruq ham config'da ko'rsatilishi mumkin; ko'rsatilmasa,
    odatdagi joylardan qidiriladi.
    """

    # whisper.cpp buyrug'i turli nomlar bilan keladi (brew: whisper-cli)
    BINARIES = ("whisper-cli", "whisper-cpp", "whisper", "main")

    # Model odatda shu joylarda yotadi (RubaiSTT Dictation ham shu yerlarga qo'yadi)
    MODEL_DIRS = (
        "~/Library/Application Support/uzbek-dictation",
        "~/Library/Application Support/RubaiSTT Dictation",
        "~/Library/Application Support/RubaiSTT",
        "~/.cache/uzbek-dictation",
        "~/.cache/whisper.cpp",
        "~/Library/Application Support/jarvis/models",
        "/Applications/RubaiSTT Dictation.app/Contents/Resources",
        "/opt/homebrew/share/whisper-cpp",
    )

    def __init__(self, model: str = "", binary: str = "", language: str = "uz",
                 threads: int = 0) -> None:
        self._model = model
        self._binary = binary
        self._language = language
        self._threads = threads
        self._resolved: tuple[str, str] | None = None

    # --- topish ---

    def _find_binary(self) -> str:
        if self._binary:
            if shutil.which(self._binary) or Path(self._binary).exists():
                return self._binary
            raise RuntimeError(
                f"whisper.cpp buyrug'i topilmadi: {self._binary}\n"
                f"O'rnatish: brew install whisper-cpp"
            )
        for name in self.BINARIES:
            found = shutil.which(name)
            if found:
                return found
        raise RuntimeError(
            "whisper.cpp topilmadi. O'rnating:\n"
            "    brew install whisper-cpp\n"
            "yoki config'da to'liq yo'lni ko'rsating: voice.stt.binary"
        )

    def _find_model(self) -> str:
        if self._model:
            path = Path(self._model).expanduser()
            if path.exists():
                return str(path)
            raise RuntimeError(f"Model fayli topilmadi: {path}")

        # Nomida "rubai" bo'lgani ustun — u o'zbekchaga o'rgatilgan
        candidates: list[Path] = []
        for folder in self.MODEL_DIRS:
            base = Path(folder).expanduser()
            if not base.is_dir():
                continue
            candidates.extend(sorted(base.rglob("*.bin")))
        for path in candidates:
            if "rubai" in path.name.lower():
                return str(path)
        if candidates:
            return str(candidates[0])
        raise RuntimeError(
            "GGML modeli topilmadi. Qaralgan joylar:\n  "
            + "\n  ".join(self.MODEL_DIRS)
            + "\nModelni topib, config'da ko'rsating: voice.stt.model\n"
              "    find ~ /Applications -iname '*.bin' -size +100M 2>/dev/null | head"
        )

    def _resolve(self) -> tuple[str, str]:
        if self._resolved is None:
            self._resolved = (self._find_binary(), self._find_model())
            log.info("whisper.cpp: %s\n            model: %s", *self._resolved)
        return self._resolved

    # --- tanish ---

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if sample_rate != 16000:
            raise ValueError(f"whisper.cpp uchun 16 kHz kerak, {sample_rate} Hz berildi")
        binary, model = self._resolve()

        # whisper.cpp fayl kutadi — vaqtinchalik WAV yozamiz va keyin o'chiramiz
        handle, wav_path = tempfile.mkstemp(prefix="jarvis-", suffix=".wav")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(to_wav_bytes(audio, sample_rate))

            args = [binary, "-m", model, "-f", wav_path,
                    "-l", self._language, "-nt", "-np"]
            if self._threads:
                args += ["-t", str(self._threads)]

            process = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            except asyncio.TimeoutError:
                process.kill()
                raise RuntimeError("whisper.cpp javob bermadi (120 s)")

            if process.returncode != 0:
                message = stderr.decode("utf-8", "replace").strip().splitlines()
                raise RuntimeError(
                    "whisper.cpp xatosi: " + (message[-1] if message else "noma'lum")
                )
            return stdout.decode("utf-8", "replace").strip()
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass


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
    # "rubai" — o'sha modelning nomi bilan chaqirish qulay bo'lsin
    if provider in ("whisper_cpp", "rubai", "rubaistt"):
        return WhisperCppStt(
            model=str(cfg.get("model", "")),
            binary=str(cfg.get("binary", "")),
            language=language,
            threads=int(cfg.get("threads", 0) or 0),
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
