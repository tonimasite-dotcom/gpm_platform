import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location("crew_install", BASE / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class AssetVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "public/dist/js").mkdir(parents=True)
        (self.root / ".env").write_text("GPM_APP_API_TOKEN=synthetic-private-server-token\n")
        (self.root / "public/mix-manifest.json").write_text(json.dumps({
            "/dist/js/app.js": "/dist/js/app.fixture.js"}))
        (self.root / "public/dist/js/app.fixture.js").write_text("loadLazyRoute()")
        (self.root / "public/dist/js/lazy.fixture.js").write_bytes(
            b"GpmCrewAttendancePanel logist_orders/gpm_crew/ \\u041e")

    def test_panel_in_lazy_chunk_is_detected(self):
        self.assertEqual(len(install.verify_assets(self.root)), 64)

    def test_server_token_in_any_chunk_is_rejected(self):
        (self.root / "public/dist/js/other.fixture.js").write_text("synthetic-private-server-token")
        with self.assertRaises(RuntimeError):
            install.verify_assets(self.root)

    def test_missing_chunk_is_rejected(self):
        (self.root / "public/dist/js/lazy.fixture.js").unlink()
        with self.assertRaises(RuntimeError):
            install.verify_assets(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
