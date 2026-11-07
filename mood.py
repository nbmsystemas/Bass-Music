"""
mood.py
-------
Motor del Reactive Mood Engine de Bass (Fusión Opción C + Opción A).

Responsabilidades:
1. Resolución de moods: a partir de un identificador o texto libre, determina
   el preset sonoro (EQ), visual (colores de curses, estilo de espectro),
   radio recomendada y prompt de IA correspondiente.
2. Orquestador de AI Stream Continuo: monitorea la playlist y coordina
   la generación en segundo plano para que el stream nunca se quede sin música.
"""

from __future__ import annotations

import re
import config


def list_mood_presets() -> list[dict]:
    """Retorna la lista de presets disponibles con sus claves y metadatos."""
    return list(config.MOOD_PRESETS.values())


def resolve_mood(query: str) -> dict:
    """
    Resuelve una consulta (sea una clave fija o texto libre) a un diccionario de mood.
    Si coincide con un preset, lo devuelve. Si es texto libre, clasifica por palabras
    clave o genera un perfil dinámico calibrado.
    """
    q = (query or "").strip().lower()
    if not q:
        return config.MOOD_PRESETS["cyberpunk"]

    # 1. Coincidencia directa por clave
    for k, preset in config.MOOD_PRESETS.items():
        if q == k or q == preset["name"].lower():
            return dict(preset)

    # 2. Heurística de palabras clave semánticas
    keywords_map = [
        (["lofi", "lo-fi", "cafe", "café", "lluvia", "rain", "cozy", "estudio", "study", "jazz", "mellow"], "lofi"),
        (["zen", "meditacion", "meditación", "paz", "calm", "relax", "ambient", "dormir", "sleep", "drone"], "zen"),
        (["cyberpunk", "neon", "matrix", "futuro", "tech", "noche", "dark synth"], "cyberpunk"),
        (["synthwave", "80s", "retro", "outrun", "arcade", "drive", "disco", "electro"], "synthwave"),
        (["rock", "metal", "guitarra", "pesado", "riff", "energia", "energía", "fuego"], "rock"),
        (["trap", "drill", "sub bass", "808", "urbano", "rap", "hip hop", "calle"], "trap"),
    ]

    for words, target_key in keywords_map:
        if any(w in q for w in words):
            base = dict(config.MOOD_PRESETS[target_key])
            base["custom_prompt"] = query.strip()
            return base

    # 3. Perfil personalizado dinámico para texto libre no categorizado
    clean_prompt = re.sub(r"[^a-zA-Z0-9\s]", " ", query).strip()
    return {
        "name": f"✨ Mood: {query[:25]}",
        "tag": "custom",
        "prompt": f"{clean_prompt} high quality stream music background",
        "custom_prompt": query.strip(),
        "eq": "Bass",
        "spec_style": 1,
        "radio": "Nightride FM (Synthwave)",
        "colors": {
            "header": "cyan",
            "selected": "magenta",
            "playing": "cyan",
            "bar_low": "blue",
            "bar_mid": "magenta",
            "bar_high": "cyan",
        },
    }


class MoodManager:
    """Gestiona el mood activo y la coordinación del stream continuo."""

    def __init__(self):
        self.active_mood: dict | None = None
        self.stream_active: bool = False
        self._variation_counter: int = 1

    def set_mood(self, mood: dict) -> None:
        self.active_mood = dict(mood)
        self._variation_counter = 1

    def clear_mood(self) -> None:
        self.active_mood = None
        self.stream_active = False

    def toggle_stream(self) -> bool:
        """Activa/desactiva el modo AI Stream Continuo."""
        self.stream_active = not self.stream_active
        return self.stream_active

    def get_status_tag(self) -> str:
        """Etiqueta compacta para la barra de estado y header."""
        if not self.active_mood:
            return ""
        name = self.active_mood.get("name", "Mood")
        stream_txt = " · [AI Stream: ON]" if self.stream_active else ""
        return f"[Mood: {name}{stream_txt}]"

    def get_next_stream_prompt(self) -> str:
        """Genera una variación armónica para el siguiente bloque del stream continuo."""
        if not self.active_mood:
            return "lofi chill background music"
        base = self.active_mood.get("custom_prompt") or self.active_mood.get("prompt", "")
        self._variation_counter += 1
        suffixes = [
            "seamless progression dynamic vibe",
            "extended flow ambient rhythm variation",
            "evolving melodic section smooth drive",
            "harmonic transition continuous mood",
        ]
        s = suffixes[(self._variation_counter) % len(suffixes)]
        return f"{base} ({s})"

    def should_queue_stream_track(self, playlist_len: int, current_index: int, is_generating: bool) -> bool:
        """
        Determina si el AI Stream debe generar el próximo bloque en segundo plano.
        Dispara cuando el stream está activo, no hay otra generación en curso
        y quedan 0 o 1 canciones antes de que se termine la playlist.
        """
        if not self.stream_active or not self.active_mood or is_generating:
            return False
        if playlist_len == 0:
            return True
        remaining = (playlist_len - 1) - current_index
        return remaining <= 0
