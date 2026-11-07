VERSION = "v1.2.0"

"""
config.py
---------
Toda la configuración "editable" de Bass vive acá: colores, teclas,
tamaños del ecualizador, etc.

Por qué un archivo aparte:
Es una práctica muy común en proyectos reales separar los "datos de
configuración" de la "lógica". Así, si mañana querés cambiar un atajo
de teclado o una paleta de colores, venís acá y no tenés que tocar
el código que realmente hace las cosas (player.py, ui.py, etc).
"""

# ---------------------------------------------------------------------------
# Atajos de teclado (usamos códigos de curses / ord() de caracteres)
# ---------------------------------------------------------------------------
KEYS = {
    "play_pause": [ord(" ")],
    "next": [ord("n")],
    "prev": [ord("p")],
    "vol_up": [ord("k"), ord("+")],
    "vol_down": [ord("j"), ord("-")],
    "seek_fwd": [ord("l")],
    "seek_back": [ord("h")],
    "add_file": [ord("a")],
    "add_url": [ord("u")],
    "add_dir": [ord("d")],
    "delete": [ord("x")],
    "search": [ord("/")],
    "toggle_eq": [ord("e")],
    "toggle_focus": [9],          # TAB
    "shuffle": [ord("s")],
    "repeat": [ord("r")],
    "mute": [ord("m")],
    "generate": [ord("g")],
    "cycle_model": [ord("G")],
    "api_key": [ord("K")],
    "mood": [ord("M")],
    "stream_toggle": [ord("S")],
    "quit": [ord("q")],
    "help": [ord("?")],
}

# ---------------------------------------------------------------------------
# Pares de color (curses.init_pair). Se inicializan en ui.py
# ---------------------------------------------------------------------------
COLOR_DEFAULT = 1
COLOR_HEADER = 2
COLOR_SELECTED = 3
COLOR_PLAYING = 4
COLOR_BAR_LOW = 5
COLOR_BAR_MID = 6
COLOR_BAR_HIGH = 7
COLOR_EQ_ACTIVE = 8
COLOR_DIM = 9
COLOR_PROGRESS = 10

# ---------------------------------------------------------------------------
# Ecualizador: 10 bandas estilo "equalizador de estéreo clásico"
# Frecuencia central de cada banda, en Hz
# ---------------------------------------------------------------------------
EQ_BANDS_HZ = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
EQ_MIN_GAIN = -12
EQ_MAX_GAIN = 12

EQ_PRESETS = {
    "Flat":     [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Bass":     [8, 6, 4, 2, 0, 0, 0, 0, 0, 0],
    "Rock":     [5, 3, -2, -4, -2, 2, 4, 5, 5, 5],
    "Pop":      [-1, 2, 4, 4, 1, -1, -1, 2, 3, 3],
    "Vocal":    [-3, -2, 0, 3, 5, 5, 3, 1, 0, -2],
    "Electro":  [6, 5, 2, 0, -2, 1, 0, 2, 4, 6],
}

# ---------------------------------------------------------------------------
# Espectro / visualizador
# ---------------------------------------------------------------------------
SPECTRUM_BARS = 120          # cantidad de barras a dibujar
SPECTRUM_FPS = 20           # actualizaciones por segundo objetivo
SAMPLE_RATE = 44100
FFT_CHUNK = 2048            # muestras que leemos por bloque de audio

# Extensiones de audio que reconocemos al escanear una carpeta local
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus", ".aac", ".wma"}

# ---------------------------------------------------------------------------
# Generación de música (cloud vía OpenRouter + fallback local MusicGen)
# ---------------------------------------------------------------------------
# Modelos disponibles (OpenRouter). Clip es el default por ser el más barato;
# Pro genera canciones más largas. Se cicla con la tecla G.
MUSIC_MODELS = [
    "google/lyria-3-clip-preview",   # clip ~30s — $0.04 (default económico)
    "google/lyria-3-pro-preview",    # canción ~3min — $0.08
]
MUSIC_DEFAULT_MODEL_INDEX = 0

# Nombre de la subcarpeta (dentro de la carpeta de música del usuario) donde
# se guardan los temas generados. Si no hay carpeta de música, se usa
# ~/.config/bass/generated.
MUSIC_OUTPUT_DIRNAME = "MusicAI"

# ---------------------------------------------------------------------------
# Reactive Mood Engine — Presets de atmósfera (Opción C + A)
# ---------------------------------------------------------------------------
MOOD_PRESETS = {
    "cyberpunk": {
        "name": "🌌 Cyberpunk Night",
        "tag": "cyberpunk",
        "prompt": "dark synthwave cyberpunk bass electronic night arpeggios 80s",
        "eq": "Bass",
        "spec_style": 1,  # Digital Shadow
        "radio": "Nightride FM (Synthwave)",
        "colors": {
            "header": "cyan",
            "selected": "magenta",
            "playing": "cyan",
            "bar_low": "blue",
            "bar_mid": "magenta",
            "bar_high": "cyan",
        },
    },
    "lofi": {
        "name": "☕ Lo-Fi Café",
        "tag": "lofi",
        "prompt": "lofi hip hop chill beats cozy rain café vinyl mellow keys",
        "eq": "Vocal",
        "spec_style": 0,  # Classic Blocks
        "radio": "Lofi Girl (YouTube Live)",
        "colors": {
            "header": "yellow",
            "selected": "magenta",
            "playing": "green",
            "bar_low": "green",
            "bar_mid": "yellow",
            "bar_high": "magenta",
        },
    },
    "zen": {
        "name": "🧘 Zen Chill",
        "tag": "zen",
        "prompt": "ambient meditation zen deep atmospheric drone calm healing peaceful",
        "eq": "Flat",
        "spec_style": 0,  # Classic Blocks
        "radio": "Drone Zone (SomaFM)",
        "colors": {
            "header": "green",
            "selected": "cyan",
            "playing": "green",
            "bar_low": "blue",
            "bar_mid": "cyan",
            "bar_high": "green",
        },
    },
    "rock": {
        "name": "⚡ Rock Energy",
        "tag": "rock",
        "prompt": "energetic rock heavy riffs punchy drums overdrive guitar rhythm drive",
        "eq": "Rock",
        "spec_style": 2,  # Pure ASCII
        "radio": "Radio Paradise (Rock)",
        "colors": {
            "header": "red",
            "selected": "yellow",
            "playing": "red",
            "bar_low": "red",
            "bar_mid": "yellow",
            "bar_high": "white",
        },
    },
    "synthwave": {
        "name": "🕶️ Synthwave 80s",
        "tag": "synthwave",
        "prompt": "outrun 1984 retro electro synthwave analog drums neon drive",
        "eq": "Electro",
        "spec_style": 1,  # Digital Shadow
        "radio": "Nightride FM (Synthwave)",
        "colors": {
            "header": "magenta",
            "selected": "cyan",
            "playing": "magenta",
            "bar_low": "magenta",
            "bar_mid": "cyan",
            "bar_high": "yellow",
        },
    },
    "trap": {
        "name": "🏙️ Dark Trap & Drill",
        "tag": "trap",
        "prompt": "dark trap sub bass 808 hard hitting hi hats drill sliding bass",
        "eq": "Bass",
        "spec_style": 1,  # Digital Shadow
        "radio": "Groove Salad (SomaFM)",
        "colors": {
            "header": "red",
            "selected": "magenta",
            "playing": "red",
            "bar_low": "red",
            "bar_mid": "magenta",
            "bar_high": "cyan",
        },
    },
}
