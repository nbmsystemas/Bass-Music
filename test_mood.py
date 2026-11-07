"""
test_mood.py
------------
Pruebas del Reactive Mood Engine y AI Stream Continuo (mood.py).
Se corre con:
    ./venv/bin/python -m unittest test_mood
"""

import unittest
import mood
import config


class TestMoodResolution(unittest.TestCase):
    def test_list_mood_presets(self):
        presets = mood.list_mood_presets()
        self.assertGreaterEqual(len(presets), 5)
        keys = [p["tag"] for p in presets]
        self.assertIn("cyberpunk", keys)
        self.assertIn("lofi", keys)
        self.assertIn("zen", keys)
        self.assertIn("rock", keys)

    def test_resolve_mood_direct_key(self):
        m = mood.resolve_mood("cyberpunk")
        self.assertEqual(m["tag"], "cyberpunk")
        self.assertEqual(m["eq"], "Bass")
        self.assertEqual(m["spec_style"], 1)

    def test_resolve_mood_case_insensitive(self):
        m = mood.resolve_mood("LoFi")
        self.assertEqual(m["tag"], "lofi")
        self.assertEqual(m["eq"], "Vocal")

    def test_resolve_mood_keywords_lofi(self):
        m = mood.resolve_mood("noche de lluvia en un café estudiando")
        self.assertEqual(m["tag"], "lofi")
        self.assertIn("custom_prompt", m)

    def test_resolve_mood_keywords_cyberpunk(self):
        m = mood.resolve_mood("luces de neon en la matrix")
        self.assertEqual(m["tag"], "cyberpunk")

    def test_resolve_mood_keywords_zen(self):
        m = mood.resolve_mood("paz y meditacion profunda para dormir")
        self.assertEqual(m["tag"], "zen")

    def test_resolve_mood_keywords_rock(self):
        m = mood.resolve_mood("guitarra pesada y riffs con energia")
        self.assertEqual(m["tag"], "rock")

    def test_resolve_mood_custom_prompt_fallback(self):
        m = mood.resolve_mood("polka intergalactica espacial")
        self.assertEqual(m["tag"], "custom")
        self.assertIn("polka intergalactica", m["prompt"])


class TestMoodManager(unittest.TestCase):
    def test_set_and_clear_mood(self):
        mgr = mood.MoodManager()
        self.assertIsNone(mgr.active_mood)
        m = mood.resolve_mood("zen")
        mgr.set_mood(m)
        self.assertEqual(mgr.active_mood["tag"], "zen")
        self.assertIn("Zen", mgr.get_status_tag())
        mgr.clear_mood()
        self.assertIsNone(mgr.active_mood)
        self.assertEqual(mgr.get_status_tag(), "")

    def test_stream_toggle(self):
        mgr = mood.MoodManager()
        self.assertFalse(mgr.stream_active)
        self.assertTrue(mgr.toggle_stream())
        self.assertTrue(mgr.stream_active)
        self.assertFalse(mgr.toggle_stream())
        self.assertFalse(mgr.stream_active)

    def test_should_queue_stream_track(self):
        mgr = mood.MoodManager()
        # Inactivo
        self.assertFalse(mgr.should_queue_stream_track(playlist_len=2, current_index=0, is_generating=False))
        
        # Activado con mood
        mgr.set_mood(mood.resolve_mood("lofi"))
        mgr.stream_active = True
        
        # Si ya hay generación en curso, False
        self.assertFalse(mgr.should_queue_stream_track(playlist_len=2, current_index=0, is_generating=True))
        
        # Si quedan temas por delante (current=0, len=3, quedan 2 temas), False
        self.assertFalse(mgr.should_queue_stream_track(playlist_len=3, current_index=0, is_generating=False))
        
        # Si está en el último tema (current=1, len=2, queda 0 tema), True!
        self.assertTrue(mgr.should_queue_stream_track(playlist_len=2, current_index=1, is_generating=False))
        
        # Si la playlist está vacía, True
        self.assertTrue(mgr.should_queue_stream_track(playlist_len=0, current_index=-1, is_generating=False))

    def test_get_next_stream_prompt(self):
        mgr = mood.MoodManager()
        mgr.set_mood(mood.resolve_mood("synthwave"))
        p1 = mgr.get_next_stream_prompt()
        p2 = mgr.get_next_stream_prompt()
        self.assertIn("outrun", p1)
        self.assertNotEqual(p1, p2)  # variaciones armónicas distintas


if __name__ == "__main__":
    unittest.main()
