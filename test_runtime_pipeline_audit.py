import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bot import _extract_supported_url, parse_edit_comment
from persistence.repository import SQLiteRepository
from video_editor import edit_video


class RuntimePipelineAudit(unittest.TestCase):
    def test_url_parser_and_persistent_edit_pipeline(self):
        url = "https://www.youtube.com/watch?v=W9XS0zSaz4c"
        self.assertEqual(_extract_supported_url(url), url)
        parsed = parse_edit_comment("خلي الإضاءة أغمق")
        self.assertTrue(parsed["understood"])
        self.assertEqual(parsed["operations"][0]["type"], "lighting")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.mp4"
            edited = root / "edited.mp4"
            db = root / "video_agent.db"

            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2",
                    "-vf", "format=yuv420p",
                    "-an",
                    str(source),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            repo = SQLiteRepository(str(db))
            repo.init_schema()
            self.assertTrue(repo.health_check())

            repo.enqueue_download_job({
                "job_id": "audit-job",
                "user_id": "audit-user",
                "url": url,
            })
            claimed = repo.claim_download_jobs()
            self.assertEqual(len(claimed), 1)
            self.assertEqual(claimed[0]["status"], "RUNNING")
            repo.complete_download_job(
                "audit-job",
                {
                    "status": "COMPLETE",
                    "video_id": "audit-video",
                    "title": "Audit video",
                    "path": str(source),
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "bytes": source.stat().st_size,
                },
            )
            self.assertEqual(repo.get_download_job("audit-job")["status"], "COMPLETE")

            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            repo.set_active_video("audit-user", "audit-video", str(source), source_sha, source.stat().st_size)
            active = repo.get_active_video("audit-user")
            self.assertEqual(active["sha256"], source_sha)

            result = edit_video(
                str(source),
                parsed["operations"][0],
                str(edited),
            )
            self.assertTrue(result.success)
            self.assertTrue(edited.is_file())
            self.assertGreater(result.artifact_bytes, 0)
            self.assertEqual(
                result.artifact_sha256,
                hashlib.sha256(edited.read_bytes()).hexdigest(),
            )

            repo.create_or_update_video_version("audit-video", result.artifact_sha256)
            repo.create_operation_log(
                {
                    "operation_id": "audit-operation",
                    "user_id": "audit-user",
                    "video_id": "audit-video",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "parent_version": source_sha,
                    "new_version": result.artifact_sha256,
                    "operation_type": "lighting",
                    "parsed_value": str(parsed["operations"][0]),
                    "generated_prompt": parsed["operations"][0]["prompt"],
                    "preview_reference": result.output_path,
                    "status": "EDITED",
                }
            )
            repo.set_active_video(
                "audit-user",
                "audit-video",
                result.output_path,
                result.artifact_sha256,
                result.artifact_bytes,
            )

            self.assertEqual(repo.get_active_video("audit-user")["sha256"], result.artifact_sha256)
            self.assertEqual(repo.get_video_version("audit-video")["current_version"], result.artifact_sha256)
            self.assertEqual(repo.get_operation_log("audit-operation")["status"], "EDITED")


if __name__ == "__main__":
    unittest.main()
