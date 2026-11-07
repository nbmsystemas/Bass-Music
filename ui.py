"""
ui.py
-----
Acá vive la interfaz de texto (TUI = Text User Interface), construida
con `curses`, el módulo estándar de Python para controlar terminales
(mover el cursor, pintar colores, capturar teclas y clicks de mouse).

Idea central: un "game loop" / "event loop". La app no espera pasivamente
input como un script normal — corre en bucle, muchas veces por segundo:
  1. Lee eventos (tecla o click) sin bloquear (curses.nodelay).
  2. Actualiza el estado (player, spectrum).
  3. Redibuja la pantalla.
Este patrón es el mismo que usan videojuegos, editores como vim/htop, etc.
"""

from __future__ import annotations

import curses
import json
import os
import pathlib
import re
import time

_UI_STATE_FILE = pathlib.Path.home() / ".config" / "bass" / "ui_state.json"

def save_ui_state(style: int, mood_tag: str | None = None) -> None:
    try:
        _UI_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"spec_style": style}
        if mood_tag:
            data["mood_tag"] = mood_tag
        _UI_STATE_FILE.write_text(json.dumps(data))
    except Exception:
        pass

def load_ui_state() -> dict:
    try:
        return json.loads(_UI_STATE_FILE.read_text())
    except Exception:
        return {"spec_style": 0, "mood_tag": "cyberpunk"}

import config
from player import Player, load_playlist, save_playlist
from spectrum import SpectrumAnalyzer
from generator import GenerationService, available_backend, output_dir, local_backend_available, api_key
from mood import MoodManager, resolve_mood, list_mood_presets



def _clean_track_title(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return "Pista sin título"
    if "youtube.com/watch" in t and "v=" in t:
        vid = t.split("v=")[1].split("&")[0]
        return f"📺 YouTube ({vid})"
    if "youtu.be/" in t:
        vid = t.split("youtu.be/")[1].split("?")[0]
        return f"📺 YouTube ({vid})"
    if "somafm.com" in t:
        station = t.split("/")[-1].split("-")[0].replace("mp3", "")
        return f"📻 SomaFM · {station.capitalize() or 'Radio'}"
    if "nightride.fm" in t:
        return "📻 Nightride FM · Synthwave"
    if "radioparadise.com" in t:
        return "📻 Radio Paradise · Rock"
    if "bbc_radio" in t or "bbc.co" in t:
        return "📻 BBC Radio 3 · Clásica"
    if "ClassicFM" in t:
        return "📻 Classic FM"
    if "spotify.com" in t:
        return "🎧 Spotify Stream"
    if t.startswith(("http://", "https://")):
        domain = t.split("//", 1)[-1].split("/")[0]
        return f"🌐 Stream: {domain}"
    m = re.match(r"^([a-zA-Z0-9_-]+)-\d{8}-\d{6}\.(mp3|wav|flac|ogg)$", t)
    if m:
        name = m.group(1).replace("-", " ").title()
        return f"✨ {name} [AI]"
    return t


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


class BassUI:
    def __init__(self, stdscr, initial_paths):
        self.scr = stdscr
        self.player = Player()
        self.spectrum = SpectrumAnalyzer()
        self.generator = GenerationService()
        self.mood_manager = MoodManager()
        ui_state = load_ui_state()
        self.spec_style = ui_state.get("spec_style", 0)
        saved_mood = resolve_mood(ui_state.get("mood_tag", "cyberpunk"))
        self.mood_manager.set_mood(saved_mood)
        if "eq" in saved_mood and saved_mood["eq"] in config.EQ_PRESETS:
            self.player.apply_preset(config.EQ_PRESETS[saved_mood["eq"]])
        self.music_model_index = config.MUSIC_DEFAULT_MODEL_INDEX

        self.focus = "library"          # "library" | "playlist" | "eq"
        self.cursor = 0                 # fila seleccionada en playlist
        self.eq_band = 0                # banda seleccionada en el EQ
        self.show_eq = True
        self.show_help = False
        self.filter_text = ""
        self._scroll = 0  # top-of-viewport index into visible rows

        m_es = os.path.expanduser("~/Música")
        m_en = os.path.expanduser("~/Music")
        if os.path.exists(m_es):
            self.lib_path = m_es
        elif os.path.exists(m_en):
            self.lib_path = m_en
        else:
            self.lib_path = os.path.expanduser("~")
        self.lib_cursor = 1
        self.lib_scroll = 0
        self.lib_items = []
        self._update_lib_items()

        self.status_msg = "Bienvenido a Bass — pulsá ? para ver la ayuda"

        # Restore playlist from last session
        for p in load_playlist():
            self._add_path(p)

        # Add any paths passed on the command line
        for p in initial_paths:
            self._add_path(p)

        self._setup_curses()
        self._show_intro_animation()

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def _show_intro_animation(self):
        """Presentación animada moderna de BASS-Music al iniciar."""
        h, w = self.scr.getmaxyx()
        if h < 18 or w < 60:
            return

        logo = [
            r"██████╗  █████╗ ███████╗███████╗    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗",
            r"██╔══██╗██╔══██╗██╔════╝██╔════╝    ████╗ ████║██║   ██║██╔════╝██║██╔════╝",
            r"██████╔╝███████║███████╗███████╗    ██╔████╔██║██║   ██║███████╗██║██║     ",
            r"██╔══██╗██╔══██║╚════██║╚════██║    ██║╚██╔╝██║██║   ██║╚════██║██║██║     ",
            r"██████╔╝██║  ██║███████║███████║    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗",
            r"╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝",
        ]
        sub = f"───  G E N T L E M A N   S T R E A M   E D I T I O N   {config.VERSION}  ───"

        self.scr.nodelay(True)
        total_steps = 14

        for step in range(total_steps):
            if self.scr.getch() != -1:
                break

            self.scr.erase()
            cur_h, cur_w = self.scr.getmaxyx()
            start_y = max(1, (cur_h - len(logo) - 6) // 2)

            color = config.COLOR_PLAYING if step % 2 == 0 else config.COLOR_PROGRESS
            for idx, line in enumerate(logo):
                x = max(0, (cur_w - len(line)) // 2)
                try:
                    self.scr.addstr(start_y + idx, x, line[:cur_w - 1], curses.color_pair(color) | curses.A_BOLD)
                except curses.error:
                    pass

            try:
                sub_x = max(0, (cur_w - len(sub)) // 2)
                self.scr.addstr(start_y + len(logo) + 1, sub_x, sub[:cur_w - 1], curses.color_pair(config.COLOR_DIM))
            except curses.error:
                pass

            bar_len = 36
            filled = int((step + 1) / total_steps * bar_len)
            pct = int((step + 1) / total_steps * 100)
            charge_bar = "━" * filled + "─" * (bar_len - filled)
            status_text = f"Initializing Audio Engine · [{charge_bar}] {pct}%"
            try:
                status_x = max(0, (cur_w - len(status_text)) // 2)
                self.scr.addstr(start_y + len(logo) + 3, status_x, status_text[:cur_w - 1], curses.color_pair(config.COLOR_HEADER))
            except curses.error:
                pass

            self.scr.refresh()
            time.sleep(0.04)

    def _setup_curses(self):
        curses.curs_set(0)
        self.scr.nodelay(True)
        self.scr.timeout(1000 // config.SPECTRUM_FPS)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        try:
            curses.mouseinterval(0)
        except Exception:
            pass

        # Paleta Gentleman / Synthwave por defecto (Rose, Magenta, Cyan, Violeta)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(config.COLOR_DEFAULT, curses.COLOR_WHITE, -1)
        curses.init_pair(config.COLOR_HEADER, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        curses.init_pair(config.COLOR_SELECTED, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(config.COLOR_PLAYING, curses.COLOR_MAGENTA, -1)
        curses.init_pair(config.COLOR_BAR_LOW, curses.COLOR_MAGENTA, -1)
        curses.init_pair(config.COLOR_BAR_MID, curses.COLOR_CYAN, -1)
        curses.init_pair(config.COLOR_BAR_HIGH, curses.COLOR_WHITE, -1)
        curses.init_pair(config.COLOR_EQ_ACTIVE, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        curses.init_pair(config.COLOR_DIM, curses.COLOR_CYAN, -1)
        curses.init_pair(config.COLOR_PROGRESS, curses.COLOR_MAGENTA, -1)

    # ------------------------------------------------------------------ #
    # Manejo de archivos / playlist
    # ------------------------------------------------------------------ #
    def _add_path(self, path: str):
        path = path.strip()
        if not path:
            return
        if path.startswith(("http://", "https://")):
            self.player.add(path)
            save_playlist(self.player.playlist)
            return
        if os.path.isdir(path):
            found = []
            for root, _dirs, files in os.walk(path, followlinks=False):
                for fname in files:
                    if os.path.splitext(fname)[1].lower() in config.AUDIO_EXTS:
                        found.append(os.path.join(root, fname))
            for f in sorted(found):
                self.player.add(f)
            save_playlist(self.player.playlist)
        elif os.path.isfile(path):
            self.player.add(path)
            save_playlist(self.player.playlist)
        else:
            self.status_msg = f"No encontrado: {path}"


    def _prompt(self, label: str) -> str:
        """Ask user for a line of text in the bottom bar with simple line editing."""
        curses.curs_set(1)
        self.scr.nodelay(False)
        h, w = self.scr.getmaxyx()
        buf = ""
        try:
            while True:
                self.scr.move(h - 1, 0)
                self.scr.clrtoeol()
                prompt = f"{label}: {buf}"
                self.scr.addstr(h - 1, 0, prompt[: w - 1])
                self.scr.refresh()
                ch = self.scr.getch()
                if ch in (10, 13):  # Enter
                    break
                elif ch in (27,):  # Esc
                    buf = ""
                    break
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    buf = buf[:-1]
                elif 32 <= ch < 256:
                    buf += chr(ch)
        finally:
            curses.curs_set(0)
            self.scr.nodelay(True)
            self.scr.timeout(1000 // config.SPECTRUM_FPS)
        return buf

    # ------------------------------------------------------------------ #
    # Generación de música, Mood Engine y configuración de API Key
    # ------------------------------------------------------------------ #
    def _apply_palette(self, colors: dict):
        if not curses.has_colors():
            return
        cmap = {
            "white": curses.COLOR_WHITE,
            "black": curses.COLOR_BLACK,
            "cyan": curses.COLOR_CYAN,
            "magenta": curses.COLOR_MAGENTA,
            "blue": curses.COLOR_BLUE,
            "green": curses.COLOR_GREEN,
            "yellow": curses.COLOR_YELLOW,
            "red": curses.COLOR_RED,
        }
        header_bg = cmap.get(colors.get("header", "cyan"), curses.COLOR_CYAN)
        sel_bg = cmap.get(colors.get("selected", "magenta"), curses.COLOR_WHITE)
        play_fg = cmap.get(colors.get("playing", "cyan"), curses.COLOR_GREEN)
        bar_low = cmap.get(colors.get("bar_low", "green"), curses.COLOR_GREEN)
        bar_mid = cmap.get(colors.get("bar_mid", "yellow"), curses.COLOR_YELLOW)
        bar_high = cmap.get(colors.get("bar_high", "red"), curses.COLOR_RED)

        curses.init_pair(config.COLOR_HEADER, curses.COLOR_BLACK, header_bg)
        curses.init_pair(config.COLOR_SELECTED, curses.COLOR_BLACK, sel_bg)
        curses.init_pair(config.COLOR_PLAYING, play_fg, -1)
        curses.init_pair(config.COLOR_PROGRESS, play_fg, -1)
        curses.init_pair(config.COLOR_EQ_ACTIVE, curses.COLOR_BLACK, play_fg)
        curses.init_pair(config.COLOR_BAR_LOW, bar_low, -1)
        curses.init_pair(config.COLOR_BAR_MID, bar_mid, -1)
        curses.init_pair(config.COLOR_BAR_HIGH, bar_high, -1)

    def _apply_mood(self, mood_dict: dict):
        self.mood_manager.set_mood(mood_dict)
        self._apply_palette(mood_dict.get("colors", {}))
        self.spec_style = mood_dict.get("spec_style", 0)
        save_ui_state(self.spec_style, mood_dict.get("tag", "cyberpunk"))
        eq_name = mood_dict.get("eq")
        if eq_name and eq_name in config.EQ_PRESETS:
            self.player.apply_preset(config.EQ_PRESETS[eq_name])
        self._update_lib_items()
        self.status_msg = f"🌌 Mood activo: {mood_dict.get('name')} | EQ: {eq_name} [S para AI Stream]"

    def _select_mood(self):
        presets = list_mood_presets()
        opts = " ".join(f"[{i+1}]{p['name'].split(' ', 1)[-1]}" for i, p in enumerate(presets))
        val = self._prompt(f"Moods 1-10: {opts} o tu texto")
        if not val or not val.strip():
            return
        clean = val.strip()
        if clean.isdigit() and 1 <= int(clean) <= len(presets):
            m = presets[int(clean) - 1]
        else:
            m = resolve_mood(clean)
        self._apply_mood(m)

    def _toggle_ai_stream(self):
        if not self.mood_manager.active_mood:
            self._apply_mood(resolve_mood("cyberpunk"))
        active = self.mood_manager.toggle_stream()
        state = "ACTIVADO (Generando en segundo plano)" if active else "PAUSADO"
        self._update_lib_items()
        self.status_msg = f"📻 AI Stream Continuo: {state}"

    def _check_ai_stream(self):
        if self.mood_manager.should_queue_stream_track(
            len(self.player.playlist),
            self.player.index,
            self.generator.is_running()
        ):
            prompt = self.mood_manager.get_next_stream_prompt()
            backend = available_backend()
            model = config.MUSIC_MODELS[self.music_model_index] if backend == "cloud" else None
            if self.generator.start(prompt, model=model):
                self.status_msg = f"📻 AI Stream: encolando '{prompt[:32]}...' en segundo plano"

    def _configure_api_key(self):
        cur = api_key()
        hint = f" (actual: {cur[:8]}...)" if cur else ""
        k = self._prompt(f"Pegá tu OPENROUTER_API_KEY{hint}")
        if k and k.strip():
            clean = k.strip()
            conf_dir = pathlib.Path.home() / ".config" / "bass"
            conf_dir.mkdir(parents=True, exist_ok=True)
            (conf_dir / "openrouter_key").write_text(clean + "\n")
            os.environ["OPENROUTER_API_KEY"] = clean
            self._update_lib_items()
            self.status_msg = "✓ OPENROUTER_API_KEY guardada en ~/.config/bass/openrouter_key"
        elif k == "":
            self.status_msg = "Configuración de API Key cancelada"

    def _start_generation(self):
        p = self._prompt("Generar música (género/mood, ej: jazz, lo-fi, trap)")
        if not p.strip():
            return
        backend = available_backend()
        if backend == "local" and not local_backend_available():
            self.status_msg = ("Sin backend: exportá OPENROUTER_API_KEY (cloud) "
                               "o instalá torch/transformers (local)")
            return
        model = config.MUSIC_MODELS[self.music_model_index] if backend == "cloud" else None
        label = model if model else "MusicGen (local)"
        if self.generator.start(p.strip(), model=model):
            self.status_msg = f"Generando '{p.strip()}' ({label})... puede tardar"
        else:
            self.status_msg = "Ya hay una generación en curso"

    def _drain_generation(self):
        state, payload = self.generator.poll()
        if state == "done" and payload:
            self._add_path(payload)
            if self.mood_manager.stream_active:
                self.player.repeat_mode = self.player.REPEAT_OFF
                if self.player.index == -1:
                    self.player.play_index(0)
                self.status_msg = f"📻 AI Stream: nuevo bloque en cola: {os.path.basename(payload)}"
            else:
                if self.player.playlist:
                    new_idx = len(self.player.playlist) - 1
                    self.player.play_index(new_idx)
                    self.player.repeat_mode = self.player.REPEAT_ONE
                    self.cursor = new_idx
                    self.focus = "playlist"
                self.status_msg = f"♪ Tema generado (loop ON): {os.path.basename(payload)}"
        elif state == "error" and payload:
            self.status_msg = f"Error generando: {payload}"

    # ------------------------------------------------------------------ #
    # Loop principal
    # ------------------------------------------------------------------ #
    def run(self):
        while True:
            self.player.drain_pending()
            self._drain_generation()
            self._check_ai_stream()
            self._draw()
            ch = self.scr.getch()
            if ch == -1:
                continue
            if ch == curses.KEY_MOUSE:
                if self._handle_mouse():
                    break
            elif self._handle_key(ch):
                break

    # ------------------------------------------------------------------ #
    # Teclado
    # ------------------------------------------------------------------ #
    def _handle_key(self, ch) -> bool:
        K = config.KEYS
        if ch in K["quit"]:
            return True
        elif ch in K["play_pause"]:
            self.player.toggle_pause()
        elif ch in K["next"]:
            self.player.next()
        elif ch in K["prev"]:
            self.player.prev()
        elif ch in K["mute"]:
            self.player.toggle_mute()
        elif ch in K["shuffle"]:
            self.player.toggle_shuffle()
            self.status_msg = f"Shuffle: {'ON' if self.player.shuffle_on else 'OFF'}"
        elif ch in K["repeat"]:
            self.player.cycle_repeat()
            names = ["OFF", "ONE", "ALL"]
            self.status_msg = f"Repeat: {names[self.player.repeat_mode]}"
        elif ch in K["generate"]:
            self._start_generation()
        elif ch in K["cycle_model"]:
            self.music_model_index = (self.music_model_index + 1) % len(config.MUSIC_MODELS)
            self.status_msg = f"Modelo música: {config.MUSIC_MODELS[self.music_model_index]}"
        elif ch in K.get("api_key", []):
            self._configure_api_key()
        elif ch in K.get("mood", []):
            self._select_mood()
        elif ch in K.get("stream_toggle", []):
            self._toggle_ai_stream()
        elif ch == ord('v'):
            self.spec_style = (getattr(self, 'spec_style', 0) + 1) % 4
            self.status_msg = f"Visualizer: Style {self.spec_style + 1}"
        elif ch in K["toggle_eq"]:
            self.show_eq = not self.show_eq
        elif ch in K["toggle_focus"]:
            if self.focus == "library":
                self.focus = "playlist"
            elif self.focus == "playlist":
                self.focus = "eq" if self.show_eq else "library"
            else:
                self.focus = "library"
        elif ch in K["help"]:
            self.show_help = not self.show_help
        elif ch in K["add_file"]:
            p = self._prompt("Ruta de archivo o carpeta")
            self._add_path(p)
        elif ch in K["add_url"]:
            p = self._prompt("URL (YouTube, SoundCloud, radio, mp3 directo...)")
            self._add_path(p)
        elif ch in K["add_dir"]:
            p = self._prompt("Carpeta a escanear")
            self._add_path(p)
        elif ch in K["search"]:
            self.filter_text = self._prompt("Buscar")
        elif ch in K["delete"]:
            if self.focus == "playlist":
                rows = self._visible_rows()
                if rows and self.cursor < len(rows):
                    real_index = rows[self.cursor][0]
                    self.player.remove(real_index)
                    save_playlist(self.player.playlist)
                    self.cursor = min(self.cursor, max(0, len(self._visible_rows()) - 1))
        elif self.focus == "eq":
            self._handle_key_eq(ch)
        elif self.focus == "library":
            self._handle_key_library(ch)
        else:
            self._handle_key_playlist(ch)
        return False

    def _handle_key_library(self, ch):
        h, w = self.scr.getmaxyx()
        visible_h = max(1, h - 12)
        if ch in (curses.KEY_UP,):
            self.lib_cursor = max(0, self.lib_cursor - 1)
            while self.lib_cursor > 0 and self.lib_items and self.lib_items[self.lib_cursor]["type"] == "header":
                self.lib_cursor -= 1
            if self.lib_cursor < self.lib_scroll:
                self.lib_scroll = self.lib_cursor
        elif ch in (curses.KEY_DOWN,):
            max_c = max(0, len(self.lib_items) - 1)
            self.lib_cursor = min(max_c, self.lib_cursor + 1)
            while self.lib_cursor < max_c and self.lib_items and self.lib_items[self.lib_cursor]["type"] == "header":
                self.lib_cursor += 1
            if self.lib_cursor >= self.lib_scroll + visible_h:
                self.lib_scroll = self.lib_cursor - visible_h + 1
        elif ch in (10, 13, curses.KEY_ENTER):
            if self.lib_items and self.lib_cursor < len(self.lib_items):
                item = self.lib_items[self.lib_cursor]
                if item["type"] == "mood":
                    self._select_mood()
                elif item["type"] == "stream_toggle":
                    self._toggle_ai_stream()
                elif item["type"] == "generate":
                    self._start_generation()
                elif item["type"] == "api_key":
                    self._configure_api_key()
                elif item["type"] == "smart":
                    keyword = item["name"].split(" ", 1)[-1].strip().lower()
                    if keyword == "zen/chill": keyword = "zen"
                    self.filter_text = keyword
                    self.focus = "playlist"
                elif item["type"] == "radio":
                    from player import save_playlist
                    self.player.add(item["url"])
                    save_playlist(self.player.playlist)
                    self.player.play_index(len(self.player.playlist) - 1)
                    self.status_msg = f"Starting radio..."
                elif item["type"] == "dir":
                    self.lib_path = item["path"]
                    self._update_lib_items()
                    self.lib_cursor = 0
                    self.lib_scroll = 0
                elif item["type"] == "file":
                    self._add_path(item["path"])
                    if self.player.playlist:
                        new_idx = len(self.player.playlist) - 1
                        self.player.play_index(new_idx)
                        self.focus = "playlist"
                        self.cursor = new_idx

    def _handle_key_playlist(self, ch):
        rows = self._visible_rows()
        h, w = self.scr.getmaxyx()
        visible_h = max(1, h - 12)  # matches playlist top/bottom (top=3, bottom=h-9)
        if ch in (curses.KEY_UP,):
            self.cursor = max(0, self.cursor - 1)
            if self.cursor < self._scroll:
                self._scroll = self.cursor
        elif ch in (curses.KEY_DOWN,):
            self.cursor = min(max(0, len(rows) - 1), self.cursor + 1)
            if self.cursor >= self._scroll + visible_h:
                self._scroll = self.cursor - visible_h + 1
        elif ch in (10, 13, curses.KEY_ENTER):
            if rows and self.cursor < len(rows):
                real_index = rows[self.cursor][0]
                self.player.play_index(real_index)
        elif ch in config.KEYS["vol_up"]:
            self.player.set_volume(+5)
        elif ch in config.KEYS["vol_down"]:
            self.player.set_volume(-5)
        elif ch in config.KEYS["seek_fwd"] or ch == curses.KEY_RIGHT:
            self.player.seek(+5)
        elif ch in config.KEYS["seek_back"] or ch == curses.KEY_LEFT:
            self.player.seek(-5)

    def _handle_key_eq(self, ch):
        if ch == curses.KEY_LEFT:
            self.eq_band = max(0, self.eq_band - 1)
        elif ch == curses.KEY_RIGHT:
            self.eq_band = min(len(config.EQ_BANDS_HZ) - 1, self.eq_band + 1)
        elif ch == curses.KEY_UP:
            g = self.player.eq_gains[self.eq_band] + 1
            self.player.set_band(self.eq_band, g)
        elif ch == curses.KEY_DOWN:
            g = self.player.eq_gains[self.eq_band] - 1
            self.player.set_band(self.eq_band, g)
        elif ch in {ord(str(d)) for d in range(1, 7)}:
            names = list(config.EQ_PRESETS.keys())
            idx = ch - ord("1")
            if idx < len(names):
                self.player.apply_preset(config.EQ_PRESETS[names[idx]])
                self.status_msg = f"Preset EQ: {names[idx]}"

    # ------------------------------------------------------------------ #
    # Mouse
    # ------------------------------------------------------------------ #
    def _handle_mouse(self) -> bool:
        try:
            _, mx, my, _, bstate = curses.getmouse()
        except curses.error:
            return False

        h, w = self.scr.getmaxyx()
        lib_w = max(25, w // 4)

        # Rueda de scroll arriba (BUTTON4)
        if bstate & (getattr(curses, "BUTTON4_PRESSED", 0) | getattr(curses, "BUTTON4_CLICKED", 0)):
            if mx < lib_w:
                self.focus = "library"
                self.lib_cursor = max(0, self.lib_cursor - 1)
                while self.lib_cursor > 0 and self.lib_items and self.lib_items[self.lib_cursor]["type"] == "header":
                    self.lib_cursor -= 1
                if self.lib_cursor < self.lib_scroll:
                    self.lib_scroll = self.lib_cursor
            else:
                self.focus = "playlist"
                self.cursor = max(0, self.cursor - 1)
                if self.cursor < self._scroll:
                    self._scroll = self.cursor
            return False

        # Rueda de scroll abajo (BUTTON5)
        if bstate & (getattr(curses, "BUTTON5_PRESSED", 0) | getattr(curses, "BUTTON5_CLICKED", 0)):
            if mx < lib_w:
                self.focus = "library"
                visible_h = max(1, h - 12)
                max_c = max(0, len(self.lib_items) - 1)
                self.lib_cursor = min(max_c, self.lib_cursor + 1)
                while self.lib_cursor < max_c and self.lib_items and self.lib_items[self.lib_cursor]["type"] == "header":
                    self.lib_cursor += 1
                if self.lib_cursor >= self.lib_scroll + visible_h:
                    self.lib_scroll = self.lib_cursor - visible_h + 1
            else:
                self.focus = "playlist"
                rows = self._visible_rows()
                visible_h = max(1, h - 12)
                self.cursor = min(max(0, len(rows) - 1), self.cursor + 1)
                if self.cursor >= self._scroll + visible_h:
                    self._scroll = self.cursor - visible_h + 1
            return False

        # Click botón 1 (con debounce para evitar disparo doble por pressed + clicked)
        is_click = bool(bstate & (curses.BUTTON1_CLICKED | getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0) | curses.BUTTON1_PRESSED))
        if is_click:
            now = time.time()
            if now - getattr(self, "_last_click_time", 0.0) < 0.25:
                return False
            self._last_click_time = now

            playlist_top, playlist_bottom = 3, h - 9
            progress_row = h - 3

            if my == progress_row:
                dur = self.player.duration
                if dur > 0:
                    frac = max(0, min(1, mx / max(1, w - 1)))
                    self.player.seek(frac * dur - self.player.position)
            elif playlist_top <= my <= playlist_bottom:
                if mx < lib_w:
                    self.focus = "library"
                    data_i = self.lib_scroll + (my - playlist_top)
                    if 0 <= data_i < len(self.lib_items):
                        if self.lib_items[data_i]["type"] != "header":
                            self.lib_cursor = data_i
                            self._handle_key_library(10)
                else:
                    self.focus = "playlist"
                    data_i = self._scroll + (my - playlist_top)
                    rows = self._visible_rows()
                    if 0 <= data_i < len(rows):
                        real_index = rows[data_i][0]
                        self.cursor = data_i
                        self.player.play_index(real_index)
        return False

    # ------------------------------------------------------------------ #
    # Helpers de datos
    # ------------------------------------------------------------------ #
    def _update_lib_items(self):
        music_dir = output_dir()
        music_dir.mkdir(parents=True, exist_ok=True)
        has_key = bool(api_key())
        key_name = "API Key: Configurada ✓" if has_key else "API Key: Pegar clave..."
        stream_name = f"AI Mood Stream: {'[ACTIVO]' if self.mood_manager.stream_active else '[APAGADO]'}"
        mood_name = f"Mood: {self.mood_manager.active_mood['name']}" if self.mood_manager.active_mood else "Elegir Mood (Ambiente/EQ)"
        self.lib_items = [
            {"type": "mood", "name": mood_name},
            {"type": "stream_toggle", "name": stream_name},
            {"type": "generate", "name": "Generar música (AI manual)"},
            {"type": "api_key", "name": key_name},
            {"type": "header", "name": "🎹 MusicAI & Stream"},
            {"type": "dir", "name": "🎼 Mis temas generados", "path": str(music_dir)},
            {"type": "header", "name": "📻 Online Radio"},
            {"name": "💻 Lofi Girl (YouTube Live)", "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk", "type": "radio"},
            {"name": "💻 Groove Salad (SomaFM)", "url": "https://ice1.somafm.com/groovesalad-256-mp3", "type": "radio"},
            {"name": "💻 DEF CON (SomaFM)", "url": "https://ice1.somafm.com/defcon-256-mp3", "type": "radio"},
            {"name": "🌃 Nightride FM (Synthwave)", "url": "https://stream.nightride.fm/nightride.m4a", "type": "radio"},
            {"name": "🧠 Drone Zone (SomaFM)", "url": "https://ice1.somafm.com/dronezone-256-mp3", "type": "radio"},
            {"name": "🧠 Deep Space One (Soma)", "url": "https://ice1.somafm.com/deepspaceone-128-mp3", "type": "radio"},
            {"name": "🎻 BBC Radio 3 (Clásica)", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_three", "type": "radio"},
            {"name": "🎻 Classic FM", "url": "http://media-ice.musicradio.com/ClassicFMMP3", "type": "radio"},
            {"name": "⚡ Radio Paradise (Rock)", "url": "http://stream.radioparadise.com/aac-320", "type": "radio"},
            {"name": "⚡ PopTron (SomaFM)", "url": "https://ice1.somafm.com/poptron-128-mp3", "type": "radio"},
            {"name": "⚡ Indie Pop Rocks!", "url": "https://ice1.somafm.com/indiepop-128-mp3", "type": "radio"},
            {"name": "⚡ Beat Blender (SomaFM)", "url": "https://ice1.somafm.com/beatblender-128-mp3", "type": "radio"},
            
            {"type": "header", "name": "🧠 Smart Mixes"},
            {"type": "smart", "name": "🎸 Rock"},
            {"type": "smart", "name": "🥁 Pop"},
            {"type": "smart", "name": "🧘 Zen/Chill"},
            {"type": "smart", "name": "🥳 Alegre"},
            
            {"type": "header", "name": "📁 Local Music"},
        ]
        
        parent = os.path.dirname(self.lib_path) if self.lib_path != "/" else "/"
        self.lib_items.append({"type": "dir", "name": "..", "path": parent})
        
        try:
            entries = os.listdir(self.lib_path)
            dirs = []
            files = []
            for e in entries:
                full = os.path.join(self.lib_path, e)
                if os.path.isdir(full):
                    dirs.append(e)
                elif os.path.isfile(full):
                    ext = os.path.splitext(e)[1].lower()
                    if ext in config.AUDIO_EXTS:
                        files.append(e)
            
            for d in sorted(dirs):
                self.lib_items.append({"type": "dir", "name": d, "path": os.path.join(self.lib_path, d)})
            for f in sorted(files):
                self.lib_items.append({"type": "file", "name": f, "path": os.path.join(self.lib_path, f)})
        except Exception:
            pass

    def _visible_rows(self):
        """Lista de (indice_real, track) filtrada por self.filter_text."""
        rows = []
        needle = self.filter_text.lower()
        for i, t in enumerate(self.player.playlist):
            if not needle or needle in t.title.lower():
                rows.append((i, t))
        return rows

    # ------------------------------------------------------------------ #
    # Dibujo
    # ------------------------------------------------------------------ #
    def _draw(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        if h < 16 or w < 40:
            self.scr.addstr(0, 0, "Enlarge the terminal to use Bass 🎧"[: w - 1])
            self.scr.refresh()
            return

        lib_w = max(25, w // 4)
        self._draw_header(w)
        self._draw_library(h, w, lib_w)
        self._draw_playlist(h, w, lib_w)
        self._draw_spectrum(h, w, lib_w)
        self._draw_progress(h, w, lib_w)
        self._draw_footer(h, w)
        if self.show_eq:
            self._draw_eq_panel(h, w)
        if self.show_help:
            self._draw_help(h, w)
        self.scr.refresh()

    def _draw_header(self, w):
        mood = self.mood_manager.active_mood
        mood_name = mood.get("name", "Cyberpunk Night") if mood else "Cyberpunk Night"
        stream_st = "ON" if self.mood_manager.stream_active else "OFF"
        title = f" 🎧 BASS MUSIC  │  {mood_name}  │  AI Stream: {stream_st}  │  {config.VERSION} "
        self.scr.attron(curses.color_pair(config.COLOR_HEADER) | curses.A_BOLD)
        try:
            self.scr.addstr(0, 0, title.center(w)[:w])
        except curses.error:
            pass
        self.scr.attroff(curses.color_pair(config.COLOR_HEADER) | curses.A_BOLD)

        status = self.status_msg
        if self.filter_text:
            status = f"[Filter: '{self.filter_text}'] {status}"
        status_line = f"  ● {status}"
        try:
            self.scr.addstr(1, 0, status_line[: w - 1].ljust(w - 1), curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

    def _draw_library(self, h, w, lib_w):
        hdr = "╭─ 📁 LIBRARY " + "─" * max(0, lib_w - 15) + "╮"
        try:
            self.scr.addstr(2, 0, hdr[:lib_w], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

        top, bottom = 3, h - 9
        visible_h = max(1, bottom - top)
        
        # separator
        for y in range(top, h - 8):
            try:
                self.scr.addstr(y, lib_w, "│", curses.color_pair(config.COLOR_DIM))
            except curses.error:
                pass
                
        self.lib_scroll = max(0, min(self.lib_scroll, max(0, len(self.lib_items) - visible_h)))
        if self.lib_items:
            self.lib_cursor = max(0, min(self.lib_cursor, len(self.lib_items) - 1))
            
        for row_i in range(visible_h):
            y = top + row_i
            data_i = self.lib_scroll + row_i
            if data_i >= len(self.lib_items):
                continue
                
            item = self.lib_items[data_i]
            if item["type"] == "header":
                line = item["name"][:lib_w - 1].ljust(lib_w - 1)
                attr = curses.color_pair(config.COLOR_DIM) | curses.A_BOLD
            else:
                prefix = "   "
                if item["type"] == "dir" and item["name"] == "..": prefix = "📁 "
                elif item["type"] == "dir": prefix = "📁 "
                elif item["type"] == "file": prefix = "🎵 "
                elif item["type"] == "generate": prefix = "✨ "
                elif item["type"] == "api_key": prefix = "🔑 "
                elif item["type"] == "mood": prefix = "🌌 "
                elif item["type"] == "stream_toggle": prefix = "📻 "
                
                line = f"{prefix}{item['name']}"
                line = line[:lib_w - 1].ljust(lib_w - 1)
                attr = curses.color_pair(config.COLOR_DEFAULT)
                
            if data_i == self.lib_cursor and self.focus == "library" and item["type"] != "header":
                attr = curses.color_pair(config.COLOR_SELECTED)
                    
            try:
                self.scr.addstr(y, 0, line, attr)
            except curses.error:
                pass

    def _draw_playlist(self, h, w, lib_w):
        eq_width = 34 if self.show_eq else 0
        list_w = max(10, w - lib_w - eq_width - 2)
        rows = self._visible_rows()

        hdr = f"╭─ 🎵 PLAYLIST [{len(rows)}] " + "─" * max(0, list_w - 20) + "╮"
        try:
            self.scr.addstr(2, lib_w + 1, hdr[:list_w], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

        top, bottom = 3, h - 9
        visible_h = max(1, bottom - top)

        # Clamp scroll
        self._scroll = max(0, min(self._scroll, max(0, len(rows) - visible_h)))
        # Clamp cursor
        if rows:
            self.cursor = max(0, min(self.cursor, len(rows) - 1))

        cur_i = self.player.index
        for row_i in range(visible_h):
            y = top + row_i
            data_i = self._scroll + row_i
            if data_i >= len(rows):
                continue
            real_i, track = rows[data_i]
            marker = "▶ " if real_i == cur_i else "  "
            display_title = _clean_track_title(track.title)
            line = f"{marker}{real_i + 1:>3}. {display_title}"
            line = line[: list_w - 1].ljust(list_w - 1)

            attr = curses.color_pair(config.COLOR_DEFAULT)
            if real_i == cur_i:
                attr = curses.color_pair(config.COLOR_PLAYING) | curses.A_BOLD
            if data_i == self.cursor and self.focus == "playlist":
                attr = curses.color_pair(config.COLOR_SELECTED)

            try:
                self.scr.addstr(y, lib_w + 1, line, attr)
            except curses.error:
                pass

        if not rows:
            hint = "Playlist empty — 'a' file, 'u' URL, 'g' generar música"
            try:
                self.scr.addstr(top, lib_w + 1, hint[: list_w - 1], curses.color_pair(config.COLOR_DIM))
            except curses.error:
                pass

    def _draw_spectrum(self, h, w, lib_w):
        levels = self.spectrum.update()

        # Si hay un tema en reproducción y sounddevice no captura audio (pactl / monitor silencioso),
        # usamos las ondas dinámicas para que el espectro NUNCA quede congelado mientras suena música.
        is_playing = (self.player.index >= 0 and not self.player.is_paused)
        if is_playing:
            try:
                max_l = float(levels.max()) if hasattr(levels, 'max') else max(levels)
            except Exception:
                max_l = 0.0
            if max_l < 0.02:
                levels = self.spectrum._fake_levels()
        elif self.player.is_paused:
            levels = [0.0] * min(len(levels), w - 2)

        spec_h = 4
        start_y = h - 7
        avail_w = w - 2
        n = min(len(levels), avail_w)
        offset_x = max(0, (w - n) // 2)

        style = getattr(self, 'spec_style', 0)

        if style == 0:
            chars = " ▂▃▄▅▆▇█"  # 1. Classic Blocks
        elif style == 1:
            chars = "░▒▓█"      # 2. Digital Shadow
        elif style == 2:
            chars = "-+*#"      # 3. Pure ASCII
        else:
            chars = "·:│┃"      # 4. Matrix Lines

        # Todos los estilos usan la paleta de degradado reactivo (Magenta -> Cyan -> White)
        c_low, c_mid, c_hi = config.COLOR_BAR_LOW, config.COLOR_BAR_MID, config.COLOR_BAR_HIGH

        title = f" L I V E   S P E C T R U M  (v = style {style+1}/4) " if (self.spectrum.live and is_playing) else f" 🎧  B A S S   S P E C T R U M  (v = style {style+1}/4) "
        try:
            self.scr.addstr(start_y - 1, max(0, (w - len(title)) // 2), title, curses.color_pair(config.COLOR_DIM))
        except Exception:
            pass

        for i in range(n):
            v = levels[i]
            val = v * spec_h
            if v < 0.4: color = c_low
            elif v < 0.7: color = c_mid
            else: color = c_hi

            for row in range(spec_h):
                y = start_y + (spec_h - 1 - row)
                cell_v = val - row
                if cell_v >= 1.0: c = chars[-1]
                elif cell_v > 0.0: c = chars[int(cell_v * (len(chars) - 1))]
                else: c = " "

                try:
                    self.scr.addstr(y, offset_x + i, c, curses.color_pair(color))
                except curses.error:
                    pass

    def _draw_progress(self, h, w, lib_w):
        row = h - 3
        pos, dur = self.player.position, self.player.duration
        frac = (pos / dur) if dur else 0
        eq_width = 34 if self.show_eq else 0
        bar_w = max(10, w - eq_width) - 1
        filled = int(bar_w * frac)
        bar = "█" * filled + "─" * (bar_w - filled)
        try:
            self.scr.addstr(row, 0, bar, curses.color_pair(config.COLOR_PROGRESS))
        except curses.error:
            pass

        state = "⏸ Paused" if self.player.is_paused else "▶ Playing"
        vol = self.player.volume
        muted = " (mute)" if self.player.is_muted else ""
        shuf = "ON" if self.player.shuffle_on else "OFF"
        rep = ["OFF", "ONE", "ALL"][self.player.repeat_mode]
        info = f"{_fmt_time(pos)} / {_fmt_time(dur)}  |  {state}  |  Vol {vol}%{muted}  |  Shuffle {shuf}  |  Loop {rep}"
        try:
            self.scr.addstr(row + 1, 0, info[: bar_w].ljust(bar_w), curses.color_pair(config.COLOR_DEFAULT))
        except curses.error:
            pass

    def _draw_footer(self, h, w):
        shortcuts = " [Space] Pausa | [M] Mood | [v] Espectro | [S] Stream IA | [g] Generar | [K] Key | [e] EQ | [a/u] Agregar | [?] Ayuda | [q] Salir"
        if w < 118:
            shortcuts = " [Space] Pausa | [M] Mood | [v] Espectro | [S] Stream | [g] IA | [K] Key | [e] EQ | [?] Ayuda | [q] Salir"
        if w < 98:
            shortcuts = " [Space] Pausa | [M] Mood | [v] Espectro | [S] Stream | [g] IA | [?] Ayuda | [q] Salir"
        if w < 78:
            shortcuts = " [Space] Pausa | [M] Mood | [v] Espectro | [?] Ayuda | [q] Salir"

        try:
            self.scr.addstr(h - 1, 0, shortcuts[: w - 1].ljust(w - 1), curses.color_pair(config.COLOR_HEADER))
        except curses.error:
            pass

    def _draw_eq_panel(self, h, w):
        eq_width = 34
        x0 = w - eq_width
        if x0 < 20:
            return
        gains = self.player.eq_gains

        header = "╭─ 🎚️ EQUALIZER (Tab) ───────╮"
        try:
            self.scr.addstr(2, x0, header[: eq_width], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

        top = 3
        bar_area_h = 10
        for bi, (freq, gain) in enumerate(zip(config.EQ_BANDS_HZ, gains)):
            col = x0 + 1 + bi * 3
            if col + 2 >= w:
                continue
            norm = (gain - config.EQ_MIN_GAIN) / (config.EQ_MAX_GAIN - config.EQ_MIN_GAIN)
            filled = int(norm * bar_area_h)
            attr = curses.color_pair(config.COLOR_DEFAULT)
            if self.focus == "eq" and bi == self.eq_band:
                attr = curses.color_pair(config.COLOR_EQ_ACTIVE) | curses.A_BOLD
            zero_r = bar_area_h // 2  # r value corresponding to 0 dB
            for r in range(bar_area_h):
                y = top + 1 + (bar_area_h - r)
                ch = "█" if r < filled else ("▪" if r == zero_r else "·")
                try:
                    self.scr.addstr(y, col, ch, attr)
                except curses.error:
                    pass
            freq_lbl = f"{freq}" if freq < 1000 else f"{freq // 1000}k"
            try:
                self.scr.addstr(top + bar_area_h + 2, col - 1, freq_lbl[:3], curses.color_pair(config.COLOR_DIM))
                self.scr.addstr(top + bar_area_h + 3, col - 1, f"{gain:+d}"[:3], attr)
            except curses.error:
                pass

        presets = list(config.EQ_PRESETS.keys())
        preset_line = "  ".join(f"{i+1}:{name}" for i, name in enumerate(presets))
        try:
            self.scr.addstr(top + bar_area_h + 5, x0, preset_line[: eq_width], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

    def _draw_help(self, h, w):
        lines = [
            "AYUDA — Bass",
            "",
            "Espacio  Play / Pausa      n / p    Siguiente / Anterior",
            "h / l    Retroceder/Avanzar 5s   ← / →   (según foco)",
            "k / j    Volumen +/-        m        Mute",
            "s        Shuffle            r        Repetir (off/una/todas)",
            "a        Agregar archivo    u        Agregar URL / stream",
            "g        Generar música     G        Ciclar modelo (clip/pro)",
            "M        Elegir Mood        S        Toggle AI Stream continuo",
            "K        Configurar API Key (o click en el menú izquierdo)",
            "API: guardada en ~/.config/bass/openrouter_key o env var",
            "d        Agregar carpeta    x        Quitar de playlist",
            "/        Buscar en playlist Tab      Cambiar foco (lista/EQ)",
            "e        Mostrar/ocultar EQ 1-6      Presets de EQ (con foco EQ)",
            "↑ / ↓    Mover selección / ajustar banda de EQ",
            "Mouse    Click en pista = reproducir | Click en barra = seek",
            "         Rueda = navegar la playlist",
            "q        Salir              ?        Cerrar esta ayuda",
        ]
        box_h = len(lines) + 2
        box_w = max(len(l) for l in lines) + 4
        y0 = max(0, (h - box_h) // 2)
        x0 = max(0, (w - box_w) // 2)
        for i in range(box_h):
            try:
                self.scr.addstr(y0 + i, x0, " " * box_w, curses.color_pair(config.COLOR_SELECTED))
            except curses.error:
                pass
        for i, l in enumerate(lines):
            truncated = l[: max(0, w - x0 - 3)]
            try:
                self.scr.addstr(y0 + 1 + i, x0 + 2, truncated, curses.color_pair(config.COLOR_SELECTED))
            except curses.error:
                pass

    def shutdown(self):
        save_playlist(self.player.playlist)
        self.spectrum.close()
        self.player.shutdown()
