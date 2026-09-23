import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from video_editor import edit_video, editor_status, ffmpeg_available


class VideoEditorAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ffmpeg_available():
            raise unittest.SkipTest("ffmpeg unavailable in test environment")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.tmp.name) / "input.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=320x568:r=12",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                "-t", "2",
                "-shortest",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                str(cls.source),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assert_artifact(self, result):
        self.assertTrue(result.success)
        self.assertTrue(Path(result.output_path).is_file())
        self.assertGreater(result.artifact_bytes, 0)
        self.assertEqual(
            result.artifact_sha256,
            hashlib.sha256(Path(result.output_path).read_bytes()).hexdigest(),
        )

    def test_01_ffmpeg_available(self): self.assertTrue(ffmpeg_available())
    def test_02_editor_ready(self): self.assertTrue(editor_status()["ready"])
    def test_03_input_exists(self): self.assertGreater(self.source.stat().st_size, 0)
    def test_04_lighting_darker(self): self.assert_artifact(edit_video(str(self.source), {"type":"lighting","value":"darker"}))
    def test_05_lighting_brighter(self): self.assert_artifact(edit_video(str(self.source), {"type":"lighting","value":"brighter"}))
    def test_06_trim(self): self.assert_artifact(edit_video(str(self.source), {"type":"trim","seconds":0.5,"position":"start"}))
    def test_07_speed_fast(self): self.assert_artifact(edit_video(str(self.source), {"type":"speed","value":"1.25x"}))
    def test_08_speed_slow(self): self.assert_artifact(edit_video(str(self.source), {"type":"speed","value":"0.85x"}))
    def test_09_zoom(self): self.assert_artifact(edit_video(str(self.source), {"type":"zoom","value":"adjust"}))
    def test_10_visual(self): self.assert_artifact(edit_video(str(self.source), {"type":"visual","value":"colors_or_filter"}))
    def test_11_unsupported(self): self.assertEqual(edit_video(str(self.source), {"type":"unknown"}).state, "FAILED")
    def test_12_missing_input(self): self.assertEqual(edit_video("/missing.mp4", {"type":"lighting"}).error_code, "EDIT_INPUT_INVALID")
    def test_13_sha_length(self):
        r = edit_video(str(self.source), {"type":"lighting","value":"darker"})
        self.assert_artifact(r); self.assertEqual(len(r.artifact_sha256), 64)
    def test_14_distinct_output(self):
        r = edit_video(str(self.source), {"type":"lighting","value":"darker"})
        self.assert_artifact(r); self.assertNotEqual(Path(r.output_path).resolve(), self.source.resolve())
    def test_15_mp4_signature(self):
        r = edit_video(str(self.source), {"type":"lighting","value":"darker"})
        self.assert_artifact(r)
        header = Path(r.output_path).read_bytes()[:8]
        self.assertGreaterEqual(int.from_bytes(header[:4], "big"), 8)
        self.assertEqual(header[4:8], b"ftyp")
    def test_16_caption_font_or_explicit_block(self):
        r = edit_video(str(self.source), {"type":"caption","new_text":"Test caption"})
        self.assertIn(r.state, ("EDITED","BLOCKED_NO_EDIT_ENGINE"))
        if r.success: self.assert_artifact(r)
    def test_17_output_nonzero(self):
        r = edit_video(str(self.source), {"type":"zoom","value":"adjust"})
        self.assert_artifact(r); self.assertGreater(os.path.getsize(r.output_path), 0)
    def test_18_repeatability(self):
        a = edit_video(str(self.source), {"type":"lighting","value":"darker"})
        b = edit_video(str(self.source), {"type":"lighting","value":"darker"})
        self.assert_artifact(a); self.assert_artifact(b)
    def test_19_no_fake_success(self):
        r = edit_video("/missing.mp4", {"type":"lighting","value":"darker"})
        self.assertNotEqual(r.state, "EDITED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
