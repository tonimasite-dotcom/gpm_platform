import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("crew_prepare", BASE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PrepareTests(unittest.TestCase):
    def sources(self):
        return {
            prepare.SYNC: """    private function request()
            $result[$this->syncOrder($order) ? 'synced' : 'deferred']++;
""",
            prepare.FORM: """import SetBrigadierForm from './SetBrigadierForm'
    SetBrigadierForm,
              <data-table ref="loaders_datatable"
""",
            prepare.SERVICE: """        $this->historyOrderService->setBrigadier($order, $brigadier);
""",
            prepare.BRIGADIER: """<base-submit-button v-if="maxLoaders && selected.length < maxLoaders" />
<base-submit-button v-if="maxLoaders && selected.length >= maxLoaders" disabled />
    title: function () {
""",
            prepare.ROUTES: """    Route::post('logist_orders/set_brigadier_to_order', [LogistOrderController::class, 'setBrigadierToOrder']);
""",
        }

    def test_targeted_patches_are_idempotent(self):
        original=self.sources()
        prepared=prepare.patches(original)
        self.assertEqual(prepare.patches(prepared),prepared)
        self.assertEqual(original,self.sources())
        self.assertIn("canAssignSelectedBrigadier",prepared[prepare.BRIGADIER])
        self.assertIn("refreshQuietly",prepared[prepare.SYNC])
        self.assertIn("gpm-crew-attendance-panel",prepared[prepare.FORM])

    def test_unsupported_source_stops_before_writing(self):
        sources=self.sources()
        sources[prepare.SERVICE]="unrelated"
        with self.assertRaises(RuntimeError):
            prepare.patches(sources)

    def test_main_crm_and_symlink_targets_are_not_accepted(self):
        with self.assertRaises(RuntimeError):
            prepare.verify_root(Path("/var/www/not-ts"))
        with self.assertRaises(RuntimeError):
            prepare.verify_root(Path("/tmp/ts.workstaffcrm.ru"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
