"""
test_generator.py
-----------------
Pruebas del motor de generación de música (generator.py) sin red:
mockeamos urllib para verificar el parseo del stream SSE de OpenRouter y
el ciclo de vida del servicio en background. Se corre con:

    ./venv/bin/python -m unittest test_generator
"""

import base64
import io
import os
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock

import generator


class FakeResponse:
    """Respuesta file-like con la forma que espera generator.OpenRouterGenerator."""

    def __init__(self, lines, code=200):
        self._lines = [l.encode("utf-8") if isinstance(l, str) else l for l in lines]
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def sse_event(payload: dict) -> str:
    return "data: " + __import__("json").dumps(payload)


def audio_event(b64: str, fmt: str = "mp3") -> dict:
    return {"choices": [{"delta": {"audio": {"data": b64, "format": fmt}}}]}


class TestBackendSelection(unittest.TestCase):
    def test_available_backend_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENROUTER_API_KEY", None)
            os.environ.pop("OPENROUTER_KEY", None)
            self.assertEqual(generator.available_backend(), "local")

    def test_available_backend_with_key(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}):
            self.assertEqual(generator.available_backend(), "cloud")


class TestHelpers(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(generator._slugify("Lo-Fi  Jazz!"), "lo-fi-jazz")
        self.assertEqual(generator._slugify("   "), "tema")

    def test_sniff_ext_by_magic_bytes(self):
        self.assertEqual(generator._sniff_ext(b"ID3\x04\x00", None), "mp3")
        self.assertEqual(generator._sniff_ext(b"RIFFxxxx", None), "wav")
        self.assertEqual(generator._sniff_ext(b"fLaCxxxx", None), "flac")
        self.assertEqual(generator._sniff_ext(b"OggSxxxx", None), "ogg")

    def test_sniff_ext_prefers_format_hint(self):
        self.assertEqual(generator._sniff_ext(b"RIFFxxxx", "mp3"), "mp3")

    def test_decode_base64_with_data_url_prefix(self):
        raw = b"RIFF-test"
        self.assertEqual(
            generator._decode_base64("data:audio/wav;base64," + base64.b64encode(raw).decode()),
            raw,
        )


class TestOpenRouterGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stem = pathlib.Path(self.tmp.name) / "tema"
        self.gen = generator.OpenRouterGenerator("sk-test", "google/lyria-3-clip-preview")

    def tearDown(self):
        self.tmp.cleanup()

    def _patch_response(self, lines):
        resp = FakeResponse(lines)
        return mock.patch("generator.urllib.request.urlopen", return_value=resp)

    def test_generate_writes_decoded_audio(self):
        c1 = base64.b64encode(b"hello-").decode()
        c2 = base64.b64encode(b"music").decode()
        lines = [
            sse_event(audio_event(c1, "mp3")),
            sse_event(audio_event(c2, "mp3")),
            "data: [DONE]",
        ]
        with self._patch_response(lines):
            path = self.gen.generate("jazz", self.stem)
        self.assertEqual(path, pathlib.Path(str(self.stem) + ".mp3"))
        self.assertEqual(path.read_bytes(), b"hello-music")

    def test_generate_sniffs_wav_when_no_format_hint(self):
        raw = b"RIFF\x00\x00\x00\x00WAVEfake"
        c = base64.b64encode(raw).decode()
        lines = [sse_event(audio_event(c, "")), "data: [DONE]"]
        with self._patch_response(lines):
            path = self.gen.generate("ambient", self.stem)
        self.assertEqual(path.suffix, ".wav")
        self.assertEqual(path.read_bytes(), raw)

    def test_generate_raises_on_no_audio(self):
        lines = [sse_event({"choices": [{"delta": {"text": "sin audio"}}]}), "data: [DONE]"]
        with self._patch_response(lines):
            with self.assertRaises(generator.MusicGenerationError):
                self.gen.generate("jazz", self.stem)

    def test_generate_raises_on_http_error(self):
        fp = io.BytesIO(b"unauthorized")
        err = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, fp)
        with mock.patch("generator.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(generator.MusicGenerationError) as cm:
                self.gen.generate("jazz", self.stem)
            self.assertIn("401", str(cm.exception))


class TestGenerationService(unittest.TestCase):
    def test_idle_when_nothing_started(self):
        svc = generator.GenerationService()
        self.assertFalse(svc.is_running())
        self.assertEqual(svc.poll(), ("idle", None))

    def test_start_and_poll_done(self):
        release = threading.Event()

        def fake_generate(self, prompt, dest_stem):
            release.wait()
            path = pathlib.Path(str(dest_stem) + ".mp3")
            path.write_bytes(b"x")
            return path

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(generator.OpenRouterGenerator, "generate", fake_generate), \
             mock.patch("generator.output_dir", return_value=pathlib.Path(td)), \
             mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}):
            svc = generator.GenerationService()
            self.assertTrue(svc.start("jazz"))
            self.assertTrue(svc.is_running())
            self.assertFalse(svc.start("otro"))  # rechazado: ya hay una en curso

            release.set()
            result = None
            for _ in range(1000):
                state, payload = svc.poll()
                if state != "running":
                    result = (state, payload)
                    break
                time.sleep(0.005)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "done")
            self.assertTrue(result[1].endswith(".mp3"))
            self.assertFalse(svc.is_running())

    def test_start_and_poll_error(self):
        def fake_generate(self, prompt, dest_stem):
            raise generator.MusicGenerationError("backend caído")

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(generator.OpenRouterGenerator, "generate", fake_generate), \
             mock.patch("generator.output_dir", return_value=pathlib.Path(td)), \
             mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}):
            svc = generator.GenerationService()
            svc.start("jazz")
            result = None
            for _ in range(1000):
                state, payload = svc.poll()
                if state != "running":
                    result = (state, payload)
                    break
                time.sleep(0.005)
            self.assertEqual(result[0], "error")
            self.assertIn("backend caído", result[1])


class TestLocalBackendAvailable(unittest.TestCase):
    def test_true_when_all_deps_present(self):
        with mock.patch("importlib.util.find_spec", return_value=object()):
            self.assertTrue(generator.local_backend_available())

    def test_false_when_a_dep_missing(self):
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(generator.local_backend_available())


if __name__ == "__main__":
    unittest.main()
