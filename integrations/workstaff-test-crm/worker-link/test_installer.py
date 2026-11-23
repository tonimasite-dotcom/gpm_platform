import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("preview_installer", BASE/"install_preview.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_console_patch_is_idempotent_and_contains_no_ui_patch(self):
        original = "before\n"+installer.ANCHOR+"\nafter\n"
        result = installer.patched(original)
        self.assertEqual(installer.patched(result), result)
        self.assertEqual(result.count(installer.HOOK), 1)
        self.assertIn("\\App\\Services\\Gpm\\GpmPreviewWorkerSync", result)
        self.assertFalse(any(path.endswith(".vue") for path in installer.FILES.values()))
        with self.assertRaises(RuntimeError):
            installer.patched("unsupported source")

    def test_only_separate_ts_database_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(installer, "ROOT", root):
                for value in [
                    "APP_URL=https://main.invalid\nDB_DATABASE=workstaff_ts_demo\n",
                    "APP_URL=https://ts.workstaffcrm.ru\nDB_DATABASE=production\n",
                ]:
                    (root/".env").write_text(value)
                    with self.assertRaises(RuntimeError):
                        installer.identity()
                (root/".env").write_text("APP_URL=https://ts.workstaffcrm.ru\nDB_DATABASE=workstaff_ts_demo\n")
                installer.identity()

    def test_flags_preserve_existing_settings_and_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); env=root/".env"
            env.write_text("PRIVATE_FIXTURE=value\nGPM_PREVIEW_WORKER_SYNC_ENABLED=true\n")
            env.chmod(0o640)
            with patch.object(installer, "ROOT", root):
                installer.settings(False, 12345)
            text = env.read_text()
            self.assertIn("PRIVATE_FIXTURE=value\n", text)
            self.assertEqual(text.count("GPM_PREVIEW_WORKER_SYNC_ENABLED="), 1)
            self.assertIn("GPM_PREVIEW_WORKER_SYNC_ENABLED=false\n", text)
            self.assertIn("GPM_PREVIEW_WORKER_SYNC_SINCE=12345\n", text)
            self.assertEqual(env.stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main(verbosity=2)
