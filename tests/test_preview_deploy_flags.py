import ast
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import yaml


class PreviewAvailabilityFlagsTests(unittest.TestCase):
    def script(self):
        path = Path(__file__).resolve().parents[1]/".github/workflows/deploy-production.yml"
        data = yaml.safe_load(path.read_text())
        step = next(s for s in data["jobs"]["deploy"]["steps"] if s.get("name") == "Deploy backend")
        match = re.search(r"<<'PYFLAGS'\n(.*?)\nPYFLAGS", step["run"], re.S)
        self.assertIsNotNone(match)
        text = match.group(1)
        old = "Path('/root/gpm-app-env')"
        self.assertEqual(text.count(old), 1)
        text = text.replace(old, "Path(os.environ['GPM_FLAGS_FIXTURE'])")
        return compile(ast.parse(text), "<deployment flags>", "exec")

    def test_preview_toggle_preserves_crew_and_other_settings(self):
        script = self.script()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"runtime-env"
            original = "PRIVATE_FIXTURE=value\nGPM_APP_CREW_ATTENDANCE_ENABLED=true\n"
            path.write_text(original)
            with patch.dict(os.environ, {"GPM_FLAGS_FIXTURE":str(path),
                "CREW_ATTENDANCE_MODE":"keep","PREVIEW_SYNC_MODE":"enable"}):
                exec(script, {})
            self.assertEqual(path.read_text(), original+"GPM_REGISTRATION_PREVIEW_CRM_ENABLED=true\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_keep_does_not_rewrite_and_invalid_mode_cannot_mutate(self):
        script = self.script()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"runtime-env"
            path.write_text("PRIVATE_FIXTURE=value\n")
            with patch.dict(os.environ, {"GPM_FLAGS_FIXTURE":str(path),
                "CREW_ATTENDANCE_MODE":"keep","PREVIEW_SYNC_MODE":"keep"}):
                exec(script, {})
                self.assertEqual(path.read_text(), "PRIVATE_FIXTURE=value\n")
                os.environ["PREVIEW_SYNC_MODE"]="bad-mode"
                with self.assertRaises(ValueError):
                    exec(script, {})
            self.assertEqual(path.read_text(), "PRIVATE_FIXTURE=value\n")
