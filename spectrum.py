"""
spectrum.py
-----------
Acá está la parte más "de ingeniería de audio" del proyecto: la barra
de espectro que se mueve al ritmo de la música.

Idea en criollo:
  1. Capturamos lo que está sonando en la PC (el audio que YA está siendo
     reproducido), leyendo del dispositivo "monitor" de PulseAudio/PipeWire.
     Es el mismo truco que usan visualizadores como `cava`.
  2. A cada bloque de muestras de audio le aplicamos una FFT (Fast Fourier
     Transform). La FFT convierte una señal en el tiempo (una onda) en
     una señal en frecuencia: "cuánta energía hay en los graves, medios
     y agudos". Es la matemática detrás de CUALQUIER ecualizador o
     visualizador de espectro.
  3. Agrupamos esas frecuencias en pocas "barras" (escala logarítmica,
     porque el oído humano percibe el sonido logarítmicamente) y
     normalizamos la altura para dibujarlas.

Si no hay un dispositivo "monitor" disponible (por ejemplo en un server
sin PulseAudio, o en el sandbox donde probé este código), Bass no se
rompe: cae a un modo "simulado" y te avisa en el README cómo activar
el real en tu máquina.
"""

from __future__ import annotations

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from queue import Queue, Empty

from config import SPECTRUM_BARS, SAMPLE_RATE, FFT_CHUNK

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except Exception:
    _HAS_SOUNDDEVICE = False


class SpectrumAnalyzer:
    def __init__(self, bars: int = SPECTRUM_BARS):
        self.bars = bars
        self.live = False
        self._stream = None
        if not _HAS_NUMPY:
            self.levels = [0.0] * bars
            self._t = 0.0
            return
        self.levels = np.zeros(bars)
        self._q: Queue = Queue(maxsize=1)
        self._buffer = np.zeros(FFT_CHUNK)
        self._t = 0.0  # reloj interno para el modo simulado

        if _HAS_SOUNDDEVICE:
            device = self._find_monitor_device()
            if device is not None:
                try:
                    self._stream = sd.InputStream(
                        device=device,
                        channels=1,
                        samplerate=SAMPLE_RATE,
                        blocksize=FFT_CHUNK,
                        callback=self._audio_callback,
                    )
                    self._stream.start()
                    self.live = True
                except Exception:
                    self._stream = None

    @staticmethod
    def _find_monitor_device():
        """Busca un dispositivo de entrada tipo 'Monitor of ...'
        (PulseAudio/PipeWire) para poder 'escuchar' la salida del sistema."""
        try:
            devices = sd.query_devices()
        except Exception:
            return None
        for i, d in enumerate(devices):
            name = d.get("name", "").lower()
            if d.get("max_input_channels", 0) > 0 and "monitor" in name:
                return i
        return None

    def _audio_callback(self, indata, frames, time_info, status):
        buf = indata[:, 0].copy()
        try:
            self._q.put_nowait(buf)
        except Exception:
            pass  # drop frame if queue full — acceptable for visualization

    # ---------------------------------------------------------------- #
    def update(self) -> np.ndarray:
        """Devuelve un array de `bars` valores entre 0.0 y 1.0, listo
        para dibujar. Hay que llamarlo en cada frame de la UI."""
        if not _HAS_NUMPY:
            return self.levels
        if self.live:
            try:
                samples = self._q.get_nowait()
                self._buffer = samples
            except Empty:
                samples = self._buffer
            samples = self._buffer
            if samples is None or len(samples) == 0:
                return self.levels
            windowed = samples * np.hanning(len(samples))
            spectrum = np.abs(np.fft.rfft(windowed))
            self.levels = self._bucketize(spectrum)
        else:
            self.levels = self._fake_levels()
        return self.levels

    def _bucketize(self, spectrum: np.ndarray) -> np.ndarray:
        # Agrupamos en bandas logarítmicas: los graves ocupan pocos bins,
        # los agudos ocupan muchísimos, así que si agrupáramos "lineal"
        # casi todas las barras mostrarían solo agudos.
        n = len(spectrum)
        edges = np.logspace(0, np.log10(n), self.bars + 1).astype(int)
        edges = np.clip(edges, 0, n - 1)
        out = np.zeros(self.bars)
        for i in range(self.bars):
            lo, hi = edges[i], max(edges[i + 1], edges[i] + 1)
            out[i] = spectrum[lo:hi].mean() if hi > lo else spectrum[lo]
        # Normalizamos con compresión logarítmica (dB-like) para que se
        # vea "vivo" sin necesitar picos gigantes.
        out = np.log1p(out)
        peak = out.max() if out.max() > 0 else 1.0
        return np.clip(out / peak, 0, 1)

    def _fake_levels(self) -> np.ndarray:
        # Animación de respaldo: ondas suaves desfasadas por barra.
        self._t += 0.15
        x = np.linspace(0, np.pi * 2, self.bars)
        wave = (np.sin(x * 2 + self._t) + 1) / 2
        wave *= (np.sin(self._t * 0.5) + 1.4) / 2.4
        return np.clip(wave, 0.05, 1)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
