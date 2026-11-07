"""
generator.py
------------
Motor de generación de música de Bass.

Dos backends, elegidos automáticamente (el usuario no distingue entre ellos):

1. Cloud — OpenRouter con Google Lyria 3 (clip/pro). Requiere la variable de
   entorno ``OPENROUTER_API_KEY``. El audio llega base64 en un stream SSE y lo
   decodificamos a un archivo local.
2. Local — MusicGen (Meta, ``facebook/musicgen-small``), gratis y sin API key,
   pero con licencia no-comercial (CC-BY-NC). Importa ``torch``/``transformers``
   en forma perezosa: si no están instalados, se informa cómo instalarlos.

La generación es LENTA (segundos para cloud, minutos para local). Por eso el
servicio corre en un thread aparte y el loop principal de la UI lo "drainea"
con ``poll()``, igual que ``player.drain_pending()``.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import threading
import time
import urllib.request
import urllib.error

import config


class MusicGenerationError(Exception):
    """Error de generación con un mensaje apto para mostrarle al usuario."""


# ---------------------------------------------------------------------------
# Configuración / resolución de rutas y credenciales
# ---------------------------------------------------------------------------
def output_dir() -> pathlib.Path:
    """Carpeta donde se guardan los temas generados."""
    for cand in ("~/Música", "~/Music"):
        p = pathlib.Path(cand).expanduser()
        if p.is_dir():
            return p / config.MUSIC_OUTPUT_DIRNAME
    return pathlib.Path.home() / ".config" / "bass" / "generated"


def api_key() -> str | None:
    """API key de OpenRouter, tomada del entorno o archivo de configuración."""
    k = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")
    if k and k.strip():
        return k.strip()
    candidates = [
        pathlib.Path(".env"),
        pathlib.Path.home() / ".config" / "bass" / "openrouter_key",
        pathlib.Path.home() / ".config" / "bass" / ".env",
    ]
    for p in candidates:
        try:
            if p.is_file():
                for line in p.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("OPENROUTER_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
                    if line.startswith("OPENROUTER_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
                    if p.name == "openrouter_key" and "=" not in line:
                        return line
        except Exception:
            pass
    return None


def available_backend() -> str:
    """'cloud' si hay API key, si no 'local' (el local puede fallar sin deps)."""
    return "cloud" if api_key() else "local"


def local_backend_available() -> bool:
    """True si están instaladas las dependencias opcionales del backend local."""
    import importlib.util
    for mod in ("torch", "transformers", "scipy"):
        if importlib.util.find_spec(mod) is None:
            return False
    return True


# ---------------------------------------------------------------------------
# Utilidades compartidas
# ---------------------------------------------------------------------------
def _slugify(prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40]
    return slug or "tema"


def _dest_stem(prompt: str) -> pathlib.Path:
    d = output_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"{_slugify(prompt)}-{time.strftime('%Y%m%d-%H%M%S')}"
    return d / name


def _decode_base64(data: str) -> bytes | None:
    """Decodifica un chunk base64, tolerando prefijo data:URL y padding faltante."""
    s = data.strip()
    if s.startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        try:
            return base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
        except Exception:
            return None


def _sniff_ext(data: bytes, fmt: str | None) -> str:
    """Determina la extensión del audio: hint del provider, luego magic bytes."""
    if fmt:
        f = fmt.lower().lstrip(".")
        if f in {"mp3", "wav", "flac", "ogg", "m4a", "aac", "opus"}:
            return f
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if data[:4] == b"RIFF":
        return "wav"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:4] == b"OggS":
        return "ogg"
    return "mp3"  # fallback: mpv detecta el codec por contenido


# ---------------------------------------------------------------------------
# Backend cloud — OpenRouter / Google Lyria 3
# ---------------------------------------------------------------------------
class OpenRouterGenerator:
    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.timeout = 300

    def generate(self, prompt: str, dest_stem: pathlib.Path) -> pathlib.Path:
        audio_bytes, fmt = self._request(prompt)
        if not audio_bytes:
            raise MusicGenerationError("No se recibió audio del modelo.")
        ext = _sniff_ext(audio_bytes, fmt)
        path = pathlib.Path(f"{dest_stem}.{ext}")
        path.write_bytes(audio_bytes)
        return path

    def _request(self, prompt: str) -> tuple[bytes, str | None]:
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["audio"],
            "stream": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.ENDPOINT,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read(400).decode("utf-8", errors="replace")
            raise MusicGenerationError(
                f"OpenRouter respondió {e.code}: {body.strip()[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise MusicGenerationError(f"No se pudo contactar OpenRouter: {e.reason}") from e

        chunks: list[bytes] = []
        fmt: str | None = None
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for data, f in self._extract_audio(obj):
                    decoded = _decode_base64(data)
                    if decoded:
                        chunks.append(decoded)
                        if f:
                            fmt = f
        return b"".join(chunks), fmt

    def _extract_audio(self, obj):
        """Extrae (data_base64, format) de cualquier clave 'audio' en el JSON."""
        found = []
        self._collect_audio(obj, found)
        for item in found:
            if isinstance(item, str):
                yield item, None
            elif isinstance(item, dict):
                data = item.get("data") or item.get("base64") or ""
                if data:
                    yield data, item.get("format")

    def _collect_audio(self, node, out):
        if isinstance(node, dict):
            if "audio" in node:
                out.append(node["audio"])
            for v in node.values():
                self._collect_audio(v, out)
        elif isinstance(node, list):
            for v in node:
                self._collect_audio(v, out)


# ---------------------------------------------------------------------------
# Backend local — MusicGen (Meta). Dependencias opcionales y lazy import.
# ---------------------------------------------------------------------------
class MusicGenGenerator:
    MODEL_ID = "facebook/musicgen-small"
    MAX_NEW_TOKENS = 1500  # ~30s de audio

    def generate(self, prompt: str, dest_stem: pathlib.Path) -> pathlib.Path:
        try:
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            import scipy.io.wavfile as wavfile
            import torch
        except ImportError as e:
            raise MusicGenerationError(
                "Backend local no disponible. Poné OPENROUTER_API_KEY=sk-or-... (cloud) "
                "o instalá: pip install torch transformers scipy accelerate"
            ) from e

        processor = AutoProcessor.from_pretrained(self.MODEL_ID)
        model = MusicgenForConditionalGeneration.from_pretrained(self.MODEL_ID)
        inputs = processor(text=[prompt], padding=True, return_tensors="pt")
        with torch.no_grad():
            audio_values = model.generate(**inputs, max_new_tokens=self.MAX_NEW_TOKENS)
        sr = model.config.audio_encoder.sampling_rate
        path = pathlib.Path(f"{dest_stem}.wav")
        wavfile.write(str(path), rate=sr, data=audio_values[0, 0].cpu().numpy())
        return path


# ---------------------------------------------------------------------------
# Servicio de generación en background (thread) + polling desde el loop de UI
# ---------------------------------------------------------------------------
class GenerationJob:
    def __init__(self, prompt: str, backend: str, model: str):
        self.prompt = prompt
        self.backend = backend
        self.model = model
        self.path: pathlib.Path | None = None
        self.error: str | None = None


class GenerationService:
    def __init__(self):
        self._job: GenerationJob | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, prompt: str, backend: str | None = None, model: str | None = None) -> bool:
        """Lanza la generación en un thread. False si ya hay una en curso."""
        with self._lock:
            if self.is_running():
                return False
            backend = backend or available_backend()
            model = model or config.MUSIC_MODELS[config.MUSIC_DEFAULT_MODEL_INDEX]
            job = GenerationJob(prompt, backend, model)
            self._job = job
            self._thread = threading.Thread(target=self._run, args=(job,), daemon=True)
            self._thread.start()
            return True

    def _run(self, job: GenerationJob):
        try:
            stem = _dest_stem(job.prompt)
            if job.backend == "cloud":
                gen = OpenRouterGenerator(api_key() or "", job.model)
            else:
                gen = MusicGenGenerator()
            job.path = gen.generate(job.prompt, stem)
        except MusicGenerationError as e:
            job.error = str(e)
        except Exception as e:  # no dejar el thread con excepción muda
            job.error = f"Error inesperado: {e}"

    def poll(self) -> tuple[str, str | None]:
        """('idle'|'running'|'done'|'error', payload)."""
        with self._lock:
            if self._job is None:
                return ("idle", None)
            if self._thread is not None and self._thread.is_alive():
                return ("running", None)
            job = self._job
            self._job = None
            self._thread = None
        if job.error:
            return ("error", job.error)
        return ("done", str(job.path))
