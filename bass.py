#!/usr/bin/env python3
"""
bass.py
-------
Punto de entrada. Este archivo es intencionalmente muy corto: su único
trabajo es leer los argumentos de la línea de comandos y arrancar la UI
dentro de `curses.wrapper`.

Por qué `curses.wrapper` y no llamar a curses "a mano":
Si tu programa crashea (una excepción no manejada) mientras curses tiene
tomada la terminal en "modo raw", te queda la terminal rota (sin eco de
teclado, colores raros, etc). `curses.wrapper` se encarga de SIEMPRE
restaurar la terminal a su estado normal al salir, incluso si hubo un
error. Es un patrón que vale la pena recordar para cualquier programa
que tome control de la terminal.
"""

import argparse
import curses
import os
import sys

# Ensure yt-dlp (and other venv binaries) are on PATH so mpv's ytdl hook
# can find them regardless of whether the venv was manually activated.
_VENV_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin")
if os.path.isdir(_VENV_BIN) and _VENV_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _VENV_BIN + os.pathsep + os.environ.get("PATH", "")

from ui import BassUI



def main():
    parser = argparse.ArgumentParser(
        prog="bass",
        description="Bass — reproductor de música profesional para la terminal",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Archivos, carpetas o URLs de streaming para cargar al iniciar",
    )
    args = parser.parse_args()

    def _run(stdscr):
        ui = BassUI(stdscr, args.paths)
        try:
            ui.run()
        finally:
            ui.shutdown()

    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Bass se cerró por un error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            curses.endwin()
        except Exception:
            pass
        sys.stdout.write("\033[?1049l\033[?25h\033[0m")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
