from __future__ import annotations

import os
import subprocess
from queue import Queue, Empty

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from config import SPECTRUM_BARS, SAMPLE_RATE, FFT_CHUNK

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except Exception:
    _HAS_SOUNDDEVICE = False


def _get_pulse_monitor() -> str | None:
    """Intenta descubrir el monitor de audio por defecto usando pactl."""
    try:
        sink = subprocess.check_output(['pactl', 'get-default-sink'], text=True).strip()
        if sink:
            return f"{sink}.monitor"
    except Exception:
        pass
    return None


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
        self._t = 0.0

        # Parámetros profesionales de suavizado (Gravedad)
        self.smoothing_up = 0.7     # Ataque rápido
        self.smoothing_down = 0.15  # Caída suave (gravedad)
        self._smooth_levels = np.zeros(bars)
        self._rolling_max = 0.01

        if _HAS_SOUNDDEVICE:
            monitor = _get_pulse_monitor()
            if monitor:
                os.environ["PULSE_SOURCE"] = monitor

            # Si pudimos forzar el monitor de Pulse/PipeWire, abrimos el stream
            # usando el backend por defecto que ahora leerá del monitor.
            try:
                self._stream = sd.InputStream(
                    channels=1,
                    samplerate=SAMPLE_RATE,
                    blocksize=FFT_CHUNK,
                    callback=self._audio_callback,
                )
                self._stream.start()
                self.live = True
            except Exception:
                self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        buf = indata[:, 0].copy()
        try:
            self._q.put_nowait(buf)
        except Exception:
            pass  # Si la cola está llena, dropeamos el frame (seguro visualmente)

    def update(self):
        if not _HAS_NUMPY:
            return self.levels

        if self.live:
            try:
                # Drenar la cola y quedarse con el chunk más reciente
                samples = None
                while not self._q.empty():
                    samples = self._q.get_nowait()
                if samples is not None:
                    self._buffer = samples
                else:
                    samples = self._buffer
            except Empty:
                samples = self._buffer

            if samples is None or len(samples) == 0:
                self.levels = np.zeros(self.bars)
                return self.levels

            # Ventana de Hanning para suavizar bordes del chunk
            windowed = samples * np.hanning(len(samples))
            # FFT (magnitud)
            spectrum = np.abs(np.fft.rfft(windowed))
            
            # Agrupar en barras
            out = self._bucketize(spectrum)

            # AGC (Control Automático de Ganancia)
            peak = out.max()
            
            # Noise gate real: si el pico es menor a 0.5 (silencio / ruido eléctrico), bajamos las barras a cero
            if peak < 0.5:
                self._smooth_levels *= (1 - self.smoothing_down)
                self.levels = np.clip(self._smooth_levels, 0, 1)
                return self.levels

            # Mantener un pico rodante para normalizar
            self._rolling_max = self._rolling_max * 0.98 + peak * 0.02
            # CLAMP: Evitar que el _rolling_max baje demasiado para no amplificar ruido de fondo
            if self._rolling_max < 3.0:
                self._rolling_max = 3.0
            
            out = out / self._rolling_max

            # Aplicar ataque y gravedad (suavizado temporal)
            for i in range(self.bars):
                if out[i] > self._smooth_levels[i]:
                    self._smooth_levels[i] = self._smooth_levels[i] * (1 - self.smoothing_up) + out[i] * self.smoothing_up
                else:
                    self._smooth_levels[i] = self._smooth_levels[i] * (1 - self.smoothing_down) + out[i] * self.smoothing_down

            self.levels = np.clip(self._smooth_levels, 0, 1)
        else:
            # Solo usar fake levels si no hay tarjeta de sonido/numpy
            self.levels = self._fake_levels()

        return self.levels

    def _bucketize(self, spectrum: np.ndarray) -> np.ndarray:
        n = len(spectrum)
        if n < 2:
            return np.zeros(self.bars)
            
        out = np.zeros(self.bars)
        
        # Logarithmic spacing for frequency bands
        edges = np.logspace(0, np.log10(n - 1), self.bars + 1)
        
        for i in range(self.bars):
            lo = edges[i]
            hi = edges[i + 1]
            
            # Sub-bin width (low frequencies) -> Interpolate
            if hi - lo < 1.0:
                center = (lo + hi) / 2
                idx = int(center)
                frac = center - idx
                if idx + 1 < n:
                    val = spectrum[idx] * (1 - frac) + spectrum[idx + 1] * frac
                else:
                    val = spectrum[idx]
                out[i] = val
            else:
                # Multi-bin width (high frequencies) -> Max peak in range
                idx_lo = int(lo)
                idx_hi = int(hi)
                if idx_hi > idx_lo and idx_hi < n:
                    out[i] = spectrum[idx_lo:idx_hi].max()
                else:
                    out[i] = spectrum[idx_lo] if idx_lo < n else 0
            
            # Pink noise compensation (boost highs to look more balanced)
            out[i] *= (1.0 + (i / self.bars) * 1.5)

        # Usar escala logaritmica (dB-like) para los valores
        return np.log1p(out * 10)

    def _fake_levels(self) -> np.ndarray:
        import random
        self._t += 0.2
        x = np.linspace(0, np.pi * 2, self.bars)
        wave = (np.sin(x * 3 + self._t) * 0.4 + 
                np.cos(x * 5 - self._t * 1.5) * 0.3 + 
                0.3)
        beat = (np.sin(self._t * 2) ** 4) * 0.5
        for i in range(min(10, self.bars)):
            wave[i] += beat * (1.0 - i/10.0)
            
        noise = np.array([random.uniform(-0.1, 0.1) for _ in range(self.bars)])
        wave = wave + noise
        return np.clip(wave, 0.02, 1.0)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
