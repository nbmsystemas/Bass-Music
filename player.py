"""
player.py
---------
Este módulo es el "motor" de Bass. No dibuja nada en pantalla: solo sabe
reproducir audio, cambiar de pista, ajustar volumen y aplicar el
ecualizador.

Concepto clave para aprender acá: NO reinventamos un decodificador de MP3
ni de FLAC. Usamos `mpv` (el reproductor de línea de comandos, escrito en
C, el mismo motor que usan reproductores como Celluloid) como "proceso
motor" y lo controlamos con la librería `python-mpv`, que habla con mpv
por IPC (un socket interno). Esto nos ahorra meses de trabajo: mpv ya
sabe decodificar decenas de formatos y reproducir streams de internet.
"""

from __future__ import annotations

import json
import os
import pathlib
import queue
import random
import threading
import mpv

from config import EQ_BANDS_HZ, EQ_MIN_GAIN, EQ_MAX_GAIN

# Playlist persistence — stored at ~/.config/bass/playlist.json
_PLAYLIST_FILE = pathlib.Path.home() / ".config" / "bass" / "playlist.json"


def save_playlist(playlist: list) -> None:
    """Persist the current playlist to disk."""
    try:
        _PLAYLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [{"path": t.path, "title": t.title} for t in playlist]
        _PLAYLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass


def load_playlist() -> list[str]:
    """Return saved paths/URLs from the last session, or [] if none."""
    try:
        data = json.loads(_PLAYLIST_FILE.read_text())
        return [item["path"] for item in data if "path" in item]
    except Exception:
        return []


class Track:
    """Representa una pista: un archivo local o una URL de streaming."""

    __slots__ = ("path", "title", "is_url")

    def __init__(self, path: str):
        self.path = path
        self.is_url = path.startswith(("http://", "https://"))
        self.title = path if self.is_url else os.path.basename(path)

    def __str__(self):
        return self.title


class Player:
    """
    Envuelve una instancia de mpv y expone una API simple:
    play(), pause(), next(), prev(), seek(), set_volume(), set_eq()...
    """

    REPEAT_OFF, REPEAT_ONE, REPEAT_ALL = range(3)

    def __init__(self):
        # ytdl=True enables the yt-dlp hook so mpv can play YouTube, SoundCloud,
        # and hundreds of other sites. yt-dlp must be available on PATH — bass.py
        # injects venv/bin at startup so the bundled yt-dlp is always found.
        self.mpv = mpv.MPV(
            ytdl=True,
            ytdl_format="bestaudio/best",
            ytdl_raw_options="extractor-args=youtube:player-client=android_creator",
            video=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
        )
        self.mpv.volume = 70

        self.playlist: list[Track] = []
        self.index: int = -1
        self.shuffle_on = False
        self.repeat_mode = self.REPEAT_OFF
        self._lock = threading.Lock()
        self._pending_eof = False

        # 10 bandas del ecualizador, todas en 0 dB al arrancar
        self.eq_gains = [0] * len(EQ_BANDS_HZ)

        # Cuando mpv termina una pista sólo, avanzamos nosotros.
        self.mpv.observe_property("eof-reached", self._on_eof)

    # ------------------------------------------------------------------ #
    # Manejo de playlist
    # ------------------------------------------------------------------ #
    def add(self, path: str) -> Track:
        track = Track(path)
        with self._lock:
            if any(t.path == path for t in self.playlist):
                return track  # silently skip duplicates
            self.playlist.append(track)
            if self.index == -1:
                self.index = 0
        return track

    def remove(self, i: int):
        with self._lock:
            if not (0 <= i < len(self.playlist)):
                return
            was_playing = i == self.index
            self.playlist.pop(i)
            if not self.playlist:
                self.index = -1
                # Schedule stop via pending flag instead of calling mpv.stop() directly
                # mpv will stop naturally; we just reset state
            elif was_playing:
                self.index = min(i, len(self.playlist) - 1)
                self._play_index_locked(self.index)
            elif i < self.index:
                self.index -= 1

    # ------------------------------------------------------------------ #
    # Reproducción
    # ------------------------------------------------------------------ #
    def _play_index_locked(self, i: int):
        """Play track i — must be called while self._lock is held."""
        if not (0 <= i < len(self.playlist)):
            return
        self.index = i
        track = self.playlist[i]
        self.mpv.play(track.path)
        self.mpv.pause = False
        self._apply_eq()

    def play_index(self, i: int):
        with self._lock:
            self._play_index_locked(i)

    def toggle_pause(self):
        with self._lock:
            if self.index == -1 and self.playlist:
                self._play_index_locked(0)
                return
        self.mpv.pause = not self.mpv.pause

    @property
    def is_paused(self) -> bool:
        try:
            return bool(self.mpv.pause)
        except Exception:
            return True

    def next(self):
        with self._lock:
            if not self.playlist:
                return
            nxt = self._compute_next(direction=1)
            self._play_index_locked(nxt)

    def prev(self):
        with self._lock:
            if not self.playlist:
                return
            nxt = self._compute_next(direction=-1)
            self._play_index_locked(nxt)

    def _compute_next(self, direction: int) -> int:
        n = len(self.playlist)
        if self.shuffle_on and n > 1:
            choices = [i for i in range(n) if i != self.index]
            return random.choice(choices)
        return (self.index + direction) % n

    def _on_eof(self, name, value):
        # Called from mpv's C thread — NEVER call mpv IPC or mutate playlist here.
        # Just set a flag; the main UI loop drains it via drain_pending().
        if value:
            self._pending_eof = True

    def drain_pending(self):
        """Call this from the main UI loop to process deferred EOF events."""
        if not self._pending_eof:
            return
        self._pending_eof = False
        with self._lock:
            if self.repeat_mode == self.REPEAT_ONE:
                self._play_index_locked(self.index)
            elif self.repeat_mode == self.REPEAT_ALL or self.shuffle_on:
                nxt = self._compute_next(direction=1)
                self._play_index_locked(nxt)
            elif self.index < len(self.playlist) - 1:
                nxt = self._compute_next(direction=1)
                self._play_index_locked(nxt)
            # else: end of list, stop naturally

    # ------------------------------------------------------------------ #
    # Volumen / seek
    # ------------------------------------------------------------------ #
    def set_volume(self, delta: int):
        vol = max(0, min(150, int(self.mpv.volume) + delta))
        self.mpv.volume = vol

    def toggle_mute(self):
        self.mpv.mute = not self.mpv.mute

    @property
    def volume(self) -> int:
        try:
            return int(self.mpv.volume or 0)
        except Exception:
            return 0

    @property
    def is_muted(self) -> bool:
        try:
            return bool(self.mpv.mute)
        except Exception:
            return False

    def seek(self, seconds: float):
        try:
            self.mpv.seek(seconds, "relative")
        except Exception:
            pass

    @property
    def position(self) -> float:
        return self.mpv.time_pos or 0.0

    @property
    def duration(self) -> float:
        return self.mpv.duration or 0.0

    # ------------------------------------------------------------------ #
    # Ecualizador — usamos el filtro de audio "equalizer" de ffmpeg/lavfi,
    # que mpv trae integrado. Encadenamos una instancia por banda:
    #   lavfi=[equalizer=f=<freq>:width_type=o:width=2:g=<ganancia>, ...]
    # ------------------------------------------------------------------ #
    def set_band(self, band_index: int, gain: int):
        gain = max(EQ_MIN_GAIN, min(EQ_MAX_GAIN, gain))
        self.eq_gains[band_index] = gain
        self._apply_eq()

    def apply_preset(self, gains: list[int]):
        self.eq_gains = list(gains)
        self._apply_eq()

    def _apply_eq(self):
        filters = ",".join(
            f"equalizer=f={freq}:width_type=o:width=2:g={gain}"
            for freq, gain in zip(EQ_BANDS_HZ, self.eq_gains)
        )
        try:
            self.mpv.af = f"lavfi=[{filters}]"
        except Exception:
            # Si el build de mpv no trae lavfi, evitamos romper la app;
            # simplemente el audio queda "plano" (sin EQ aplicada).
            pass

    # ------------------------------------------------------------------ #
    def toggle_shuffle(self):
        self.shuffle_on = not self.shuffle_on

    def cycle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3

    def shutdown(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass
