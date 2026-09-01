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
import pathlib

_UI_STATE_FILE = pathlib.Path.home() / ".config" / "bass" / "ui_state.json"

def save_ui_state(style: int) -> None:
    try:
        _UI_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _UI_STATE_FILE.write_text(json.dumps({"spec_style": style}))
    except:
        pass

def load_ui_state() -> int:
    try:
        return json.loads(_UI_STATE_FILE.read_text()).get("spec_style", 0)
    except:
        return 0

import os

import config
from player import Player, load_playlist, save_playlist
from spectrum import SpectrumAnalyzer



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

        self.focus = "library"          # "library" | "playlist" | "eq"
        self.cursor = 0                 # fila seleccionada en playlist
        self.eq_band = 0                # banda seleccionada en el EQ
        self.show_eq = True
        self.show_help = False
        self.spec_style = load_ui_state()
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
        self.lib_cursor = 0
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

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def _setup_curses(self):
        curses.curs_set(0)
        self.scr.nodelay(True)
        self.scr.timeout(1000 // config.SPECTRUM_FPS)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        try:
            curses.mouseinterval(0)
        except Exception:
            pass

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(config.COLOR_DEFAULT, curses.COLOR_WHITE, -1)
        curses.init_pair(config.COLOR_HEADER, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(config.COLOR_SELECTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(config.COLOR_PLAYING, curses.COLOR_GREEN, -1)
        curses.init_pair(config.COLOR_BAR_LOW, curses.COLOR_GREEN, -1)
        curses.init_pair(config.COLOR_BAR_MID, curses.COLOR_YELLOW, -1)
        curses.init_pair(config.COLOR_BAR_HIGH, curses.COLOR_RED, -1)
        curses.init_pair(config.COLOR_EQ_ACTIVE, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(config.COLOR_DIM, curses.COLOR_WHITE, -1)
        curses.init_pair(config.COLOR_PROGRESS, curses.COLOR_CYAN, -1)

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
    # Loop principal
    # ------------------------------------------------------------------ #
    def run(self):
        while True:
            self.player.drain_pending()
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
        visible_h = max(1, h - 9)
        if ch in (curses.KEY_UP,):
            self.lib_cursor = max(0, self.lib_cursor - 1)
            if self.lib_cursor < self.lib_scroll:
                self.lib_scroll = self.lib_cursor
        elif ch in (curses.KEY_DOWN,):
            self.lib_cursor = min(max(0, len(self.lib_items) - 1), self.lib_cursor + 1)
            if self.lib_cursor >= self.lib_scroll + visible_h:
                self.lib_scroll = self.lib_cursor - visible_h + 1
        elif ch in (10, 13, curses.KEY_ENTER):
            if self.lib_items and self.lib_cursor < len(self.lib_items):
                item = self.lib_items[self.lib_cursor]
                if item["type"] == "smart":
                    keyword = item["name"].split(" ", 1)[-1].strip().lower()
                    if keyword == "zen/chill": keyword = "zen"
                    self.filter_text = keyword
                    self.focus = "playlist"
                elif item["type"] == "dir":
                    self.lib_path = item["path"]
                    self._update_lib_items()
                    self.lib_cursor = 0
                    self.lib_scroll = 0
                elif item["type"] == "file":
                    self._add_path(item["path"])

    def _handle_key_playlist(self, ch):
        rows = self._visible_rows()
        h, w = self.scr.getmaxyx()
        visible_h = max(1, h - 8 - 2)  # matches playlist top/bottom
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

        # Scroll del mouse sobre la playlist
        if bstate & getattr(curses, "BUTTON4_PRESSED", 0):
            self.cursor = max(0, self.cursor - 1)
            if self.cursor < self._scroll:
                self._scroll = self.cursor
            return False
        if bstate & getattr(curses, "BUTTON5_PRESSED", 0):
            rows = self._visible_rows()
            h_inner, _ = self.scr.getmaxyx()
            visible_h = max(1, h_inner - 9 - 2)
            self.cursor = min(max(0, len(rows) - 1), self.cursor + 1)
            if self.cursor >= self._scroll + visible_h:
                self._scroll = self.cursor - visible_h + 1
            return False

        if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_DOUBLE_CLICKED:
            lib_w = max(25, w // 4)
            playlist_top, playlist_bottom = 2, h - 9
            progress_row = h - 4

            if my == progress_row:
                dur = self.player.duration
                if dur > 0:
                    frac = max(0, min(1, mx / max(1, w - 1)))
                    self.player.seek(frac * dur - self.player.position)
            elif playlist_top <= my < playlist_bottom:
                if mx < lib_w:
                    self.focus = "library"
                    data_i = self.lib_scroll + (my - playlist_top)
                    if 0 <= data_i < len(self.lib_items):
                        self.lib_cursor = data_i
                        if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                            self._handle_key_library(10)
                else:
                    self.focus = "playlist"
                    data_i = self._scroll + (my - playlist_top)
                    rows = self._visible_rows()
                    if data_i < len(rows):
                        real_index = rows[data_i][0]
                        self.cursor = data_i
                        if bstate & curses.BUTTON1_DOUBLE_CLICKED or bstate & curses.BUTTON1_CLICKED:
                            self.player.play_index(real_index)
        return False

    # ------------------------------------------------------------------ #
    # Helpers de datos
    # ------------------------------------------------------------------ #
    def _update_lib_items(self):
        self.lib_items = [
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
        title = " BASS -- terminal music player "
        self.scr.attron(curses.color_pair(config.COLOR_HEADER))
        try:
            self.scr.addstr(0, 0, title.ljust(w)[:w])
        except curses.error:
            pass
        self.scr.attroff(curses.color_pair(config.COLOR_HEADER))
        status = self.status_msg
        if self.filter_text:
            status = f"[Filter: '{self.filter_text}'] {status}"
        try:
            self.scr.addstr(1, 0, status[: w - 1], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

    def _draw_library(self, h, w, lib_w):
        top, bottom = 1, h - 9
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
                prefix = "  "
                if item["type"] == "dir": prefix = "📁 "
                elif item["type"] == "file": prefix = "🎵 "
                elif item["type"] == "smart": prefix = "   "
                line = f"{prefix}{item['name']}"
                line = line[:lib_w - 1].ljust(lib_w - 1)
                
                attr = curses.color_pair(config.COLOR_DEFAULT)
                if data_i == self.lib_cursor and self.focus == "library":
                    attr = curses.color_pair(config.COLOR_SELECTED)
                    
            try:
                self.scr.addstr(y, 0, line, attr)
            except curses.error:
                pass

    def _draw_playlist(self, h, w, lib_w):
        top, bottom = 1, h - 9  # fixed: was h-8, now h-9 to avoid spectrum label collision (M-5)
        eq_width = 34 if self.show_eq else 0
        list_w = max(10, w - lib_w - eq_width - 2)
        visible_h = max(1, bottom - top)

        rows = self._visible_rows()
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
            line = f"{marker}{real_i + 1:>3}. {track.title}"
            line = line[: list_w - 1].ljust(list_w - 1)

            attr = curses.color_pair(config.COLOR_DEFAULT)
            if data_i == self.cursor and self.focus == "playlist":
                attr = curses.color_pair(config.COLOR_SELECTED)
            elif real_i == cur_i:
                attr = curses.color_pair(config.COLOR_PLAYING) | curses.A_BOLD

            try:
                self.scr.addstr(y, lib_w + 1, line, attr)
            except curses.error:
                pass

        if not rows:
            hint = "Playlist empty — press 'a' to add a file, 'u' for a URL"
            try:
                self.scr.addstr(top, lib_w + 1, hint[: list_w - 1], curses.color_pair(config.COLOR_DIM))
            except curses.error:
                pass

    def _draw_spectrum(self, h, w, lib_w):
        levels = self.spectrum.update()
        spec_h = 4
        start_y = h - 7
        avail_w = w - 2
        n = min(len(levels), avail_w)
        offset_x = max(0, (w - n) // 2)
        
        style = getattr(self, 'spec_style', 0)
        
        if style == 0:
            chars = "  ▂▃▄▅▆▇█"  # Classic Gradient
            c_low, c_mid, c_hi = config.COLOR_BAR_LOW, config.COLOR_BAR_MID, config.COLOR_BAR_HIGH
        elif style == 1:
            chars = " ││││"      # Thin Lines (Professional/Clean)
            c_low, c_mid, c_hi = config.COLOR_HEADER, config.COLOR_HEADER, config.COLOR_HEADER
        elif style == 2:
            chars = " ·•●*"      # Dots (Retro)
            c_low, c_mid, c_hi = config.COLOR_SELECTED, config.COLOR_SELECTED, config.COLOR_SELECTED
        else:
            chars = " ░▒▓█"      # Digital / Cyberpunk
            c_low, c_mid, c_hi = config.COLOR_PLAYING, config.COLOR_PLAYING, config.COLOR_PLAYING
            
        title = f" L I V E   S P E C T R U M  (v = style {style+1}/4) " if self.spectrum.live else " ( S I M U L A T E D ) "
        try:
            self.scr.addstr(start_y - 1, max(0, (w - len(title)) // 2), title, curses.color_pair(config.COLOR_DIM))
        except:
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
        info = f"{_fmt_time(pos)} / {_fmt_time(dur)}"
        try:
            self.scr.addstr(row + 1, 0, info[: bar_w], curses.color_pair(config.COLOR_DEFAULT))
        except curses.error:
            pass

    def _draw_footer(self, h, w):
        state = "II Paused" if self.player.is_paused else "▶ Playing"
        vol = self.player.volume
        muted = " (mute)" if self.player.is_muted else ""
        shuf = "ON" if self.player.shuffle_on else "OFF"
        rep = ["OFF", "ONE", "ALL"][self.player.repeat_mode]
        line = f"{state} | Vol {vol}%{muted} | Shuffle {shuf} | Repetir {rep} | ? = ayuda"
        try:
            self.scr.addstr(h - 1, 0, line[: w - 1], curses.color_pair(config.COLOR_DIM))
        except curses.error:
            pass

    def _draw_eq_panel(self, h, w):
        eq_width = 34
        x0 = w - eq_width
        if x0 < 20:
            return
        gains = self.player.eq_gains
        top = 2
        header = " EQUALIZER (Tab to focus) "
        try:
            self.scr.addstr(top, x0, header[: eq_width], curses.A_BOLD)
        except curses.error:
            pass

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
