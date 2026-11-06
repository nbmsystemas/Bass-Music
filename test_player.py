"""
test_player.py
--------------
Pruebas de la lógica de avance / shuffle / repeat del Player, con un mpv
falso (sin audio ni pantalla). Verifica que el fin de pista (core-idle)
avanza correctamente y que el idle inicial se ignora. Se corre con:

    ./venv/bin/python -m unittest test_player
"""

import unittest
from unittest import mock

import player as player_module


class FakeMPV:
    def __init__(self, *a, **kw):
        self.volume = 50
        self.mute = False
        self.pause = False
        self.af = ""
        self.played = []

    def observe_property(self, name, cb):
        self._on = (name, cb)

    def play(self, path):
        self.played.append(path)

    def terminate(self):
        pass


def make_player():
    with mock.patch.object(player_module.mpv, "MPV", FakeMPV):
        p = player_module.Player()
    return p


class TestPlayerAdvance(unittest.TestCase):
    def test_idle_advances_to_next(self):
        p = make_player()
        for t in ("a.mp3", "b.mp3", "c.mp3"):
            p.add(t)
        p.play_index(0)
        p._on_idle("core-idle", True)
        self.assertTrue(p._pending_eof)
        p.drain_pending()
        self.assertEqual(p.index, 1)

    def test_idle_ignored_before_first_play(self):
        p = make_player()
        p.add("a.mp3")  # index pasa a 0, pero aún no se reprodujo nada
        p._on_idle("core-idle", True)
        self.assertFalse(p._pending_eof)

    def test_repeat_one_loops(self):
        p = make_player()
        for t in ("a.mp3", "b.mp3", "c.mp3"):
            p.add(t)
        p.repeat_mode = p.REPEAT_ONE
        p.play_index(1)
        p._on_idle("core-idle", True)
        p.drain_pending()
        self.assertEqual(p.index, 1)

    def test_repeat_all_wraps(self):
        p = make_player()
        for t in ("a.mp3", "b.mp3", "c.mp3"):
            p.add(t)
        p.repeat_mode = p.REPEAT_ALL
        p.play_index(2)
        p._on_idle("core-idle", True)
        p.drain_pending()
        self.assertEqual(p.index, 0)

    def test_repeat_off_stops_at_last(self):
        p = make_player()
        for t in ("a.mp3", "b.mp3"):
            p.add(t)
        p.play_index(1)
        p._on_idle("core-idle", True)
        p.drain_pending()
        self.assertEqual(p.index, 1)  # no avanza más allá del final

    def test_shuffle_next_picks_other_index(self):
        p = make_player()
        for t in ("a.mp3", "b.mp3", "c.mp3"):
            p.add(t)
        p.toggle_shuffle()
        p.play_index(0)
        p.next()
        self.assertIn(p.index, (1, 2))


if __name__ == "__main__":
    unittest.main()
