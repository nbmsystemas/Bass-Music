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
                samples = self._q.get_nowait()
                self._buffer = samples
            except Empty:
                samples = self._buffer

            if samples is None or len(samples) == 0:
                return self.levels

            windowed = samples * np.hanning(len(samples))
            spectrum = np.abs(np.fft.rfft(windowed))
            out = self._bucketize(spectrum)

            # AGC (Control Automático de Ganancia) y Suavizado
            peak = out.max()
            
            # Si hay silencio absoluto (ej. cargando stream o mic apagado), usamos el fake_levels para que se vea profesional y siempre vivo
            if peak < 0.005:
                self.levels = self._fake_levels()
                return self.levels

            self._rolling_max = self._rolling_max * 0.95 + peak * 0.05
            if self._rolling_max < 0.01:
                self._rolling_max = 0.01
            
            out = out / self._rolling_max

            # Aplicar ataque y gravedad
            for i in range(self.bars):
                if out[i] > self._smooth_levels[i]:
                    self._smooth_levels[i] = self._smooth_levels[i] * (1 - self.smoothing_up) + out[i] * self.smoothing_up
                else:
                    self._smooth_levels[i] = self._smooth_levels[i] * (1 - self.smoothing_down) + out[i] * self.smoothing_down

            self.levels = np.clip(self._smooth_levels, 0, 1)
        else:
            self.levels = self._fake_levels()

        return self.levels

    def _bucketize(self, spectrum: np.ndarray) -> np.ndarray:
        # Rango de audición útil: cortamos los subs muy bajos y los ultrasónicos
        n = len(spectrum)
        if n < 2:
            return np.zeros(self.bars)
            
        # Distribución logarítmica de bandas (parecido a Mel-scale)
        edges = np.logspace(0, np.log10(n - 1), self.bars + 1).astype(int)
        
        out = np.zeros(self.bars)
        for i in range(self.bars):
            lo, hi = edges[i], edges[i + 1]
            if hi <= lo:
                hi = lo + 1
            if hi > n:
                hi = n
            out[i] = spectrum[lo:hi].mean() if hi > lo else 0.0
            
            # Compensación Pink Noise (los agudos tienen menos energía natural, los subimos visualmente)
            out[i] *= (1.0 + (i / self.bars) * 2.5)

        return np.log1p(out)

    def _fake_levels(self) -> np.ndarray:
        import random
        self._t += 0.2
        x = np.linspace(0, np.pi * 2, self.bars)
        # Combine multiple sine waves and some random noise for a realistic "music" look
        wave = (np.sin(x * 3 + self._t) * 0.4 + 
                np.cos(x * 5 - self._t * 1.5) * 0.3 + 
                0.3)
        # Add a bass beat effect on the left side
        beat = (np.sin(self._t * 2) ** 4) * 0.5
        for i in range(min(10, self.bars)):
            wave[i] += beat * (1.0 - i/10.0)
            
        # Add micro-noise
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
