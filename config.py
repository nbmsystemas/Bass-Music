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
SPECTRUM_BARS = 28          # cantidad de barras a dibujar
SPECTRUM_FPS = 20           # actualizaciones por segundo objetivo
SAMPLE_RATE = 44100
FFT_CHUNK = 1024            # muestras que leemos por bloque de audio

# Extensiones de audio que reconocemos al escanear una carpeta local
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus", ".aac", ".wma"}
