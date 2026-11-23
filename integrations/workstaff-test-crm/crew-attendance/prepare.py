"""Reversible, targeted TS source preparation. No database or environment writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path("/var/www/gruzpiter/data/www/ts.workstaffcrm.ru")
PACKAGE_FILES = {
    "GpmCrewBridgePolicy.php": "app/Services/Order/GpmCrewBridgePolicy.php",
    "GpmCrewAttendanceService.php": "app/Services/Order/GpmCrewAttendanceService.php",
    "GpmCrewAttendanceController.php": "app/Http/Controllers/Order/GpmCrewAttendanceController.php",
    "GpmCrewAttendancePanel.vue": "resources/js/pages/app/orders/logist_orders/GpmCrewAttendancePanel.vue",
}
SYNC = "app/Services/Order/GpmAppOrderSync.php"
FORM = "resources/js/pages/app/orders/logist_orders/LogistOrderForm.vue"
SERVICE = "app/Services/Order/LogistOrderService.php"
BRIGADIER = "resources/js/pages/app/orders/logist_orders/SetBrigadierForm.vue"
ROUTES = "routes/api.php"


def replace_once(text, old, new, path):
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError("Unsupported source anchor: " + path)
    return text.replace(old, new)


def patches(sources):
    result = {}
    method = """    public function crewOrderNumber(Order $order): ?string
    {
        if (!$this->enabled() || !$this->linked($order)) return null;
        return $this->locked((int) $order->id, function () use ($order) {
            $state = json_decode(file_get_contents($this->statePath((int) $order->id)), true, 512, JSON_THROW_ON_ERROR);
            $number = (string) ($state['order_number'] ?? '');
            return $number !== '' && $number === (string) $order->order_number ? $number : null;
        });
    }

"""
    text = sources[SYNC]
    if "public function crewOrderNumber(" not in text:
        text = replace_once(text, "    private function request()\n", method + "    private function request()\n", SYNC)
    old = "            $result[$this->syncOrder($order) ? 'synced' : 'deferred']++;"
    text = replace_once(text, old, old + "\n            app(GpmCrewAttendanceService::class)->refreshQuietly($order);", SYNC)
    result[SYNC] = text

    text = sources[FORM]
    text = replace_once(text, "import SetBrigadierForm from './SetBrigadierForm'",
                        "import GpmCrewAttendancePanel from './GpmCrewAttendancePanel'\nimport SetBrigadierForm from './SetBrigadierForm'", FORM)
    text = replace_once(text, "    SetBrigadierForm,",
                        "    GpmCrewAttendancePanel,\n    SetBrigadierForm,", FORM)
    old = '              <data-table ref="loaders_datatable"'
    text = replace_once(text, old, '              <gpm-crew-attendance-panel v-if="modelId" :order-id="modelId" />\n' + old, FORM)
    result[FORM] = text

    text = sources[SERVICE]
    old = "        $this->historyOrderService->setBrigadier($order, $brigadier);"
    text = replace_once(text, old, old +
        "\n        app(\\App\\Services\\Order\\GpmCrewAttendanceService::class)->syncLeaderQuietly($order, auth()->user());", SERVICE)
    result[SERVICE] = text

    text = sources[BRIGADIER]
    if "canAssignSelectedBrigadier" not in text:
        buttons = list(re.finditer(r"<base-submit-button\b[\s\S]*?/>", text))
        buttons = [m for m in buttons if "selected.length" in m.group(0)]
        if len(buttons) != 2:
            raise RuntimeError("Unsupported brigadier capacity controls")
        replacement = '<base-submit-button caption="Назначить" :form="form" :disabled="!canAssignSelectedBrigadier" />'
        text = text[:buttons[0].start()] + replacement + text[buttons[1].end():]
        computed = """    canAssignSelectedBrigadier () {
      const id = Number(this.form.selected_id)
      const assigned = this.selected.map(item => Number(item && typeof item === 'object' ? item.id : item))
      return Number(this.maxLoaders) > 0 && id > 0 &&
        (assigned.includes(id) || assigned.length < Number(this.maxLoaders))
    },
"""
        text = replace_once(text, "    title: function () {", computed + "    title: function () {", BRIGADIER)
    result[BRIGADIER] = text

    text = sources[ROUTES]
    old = "    Route::post('logist_orders/set_brigadier_to_order', [LogistOrderController::class, 'setBrigadierToOrder']);"
    route = """    Route::post('logist_orders/gpm_crew/{operation}', [\\App\\Http\\Controllers\\Order\\GpmCrewAttendanceController::class, 'handle'])
        ->where('operation', 'state|link|roster|enable|review');
"""
    text = replace_once(text, old, route + old, ROUTES)
    result[ROUTES] = text
    return result


def build(root, package):
    sources = {p: (root / p).read_text(encoding="utf-8") for p in [SYNC, FORM, SERVICE, BRIGADIER, ROUTES]}
    result = patches(sources)
    for name, target in PACKAGE_FILES.items():
        result[target] = (package / name).read_text(encoding="utf-8")
    return result


def verify_root(root):
    if root != ROOT or root.resolve() != ROOT or not root.is_dir():
        raise RuntimeError("Only the verified TS installation may be prepared")
    content = (root / ".env").read_text(encoding="utf-8")
    values = []
    for line in content.splitlines():
        fields = line.split("=", 1)
        if len(fields) == 2 and fields[0].strip() == "APP_URL":
            values.append(fields[1].strip().strip(chr(34) + chr(39)).rstrip("/"))
    if values != ["https://ts.workstaffcrm.ru"]:
        raise RuntimeError("TS application identity does not match")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--backup", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    verify_root(root)
    backup = Path(args.backup)
    if backup.parent != Path("/root") or not backup.name.startswith("gpm-ts-crew-") or backup.exists():
        raise RuntimeError("A new absolute private backup directory is required")
    changes = build(root, Path(__file__).resolve().parent)
    for rel in changes:
        target = root / rel
        if not str(target.resolve()).startswith(str(ROOT) + "/"):
            raise RuntimeError("Target escapes TS root")
    if not args.write:
        print(json.dumps({"prepared_files": len(changes), "write": False}))
        return
    backup.mkdir(mode=0o700, parents=False)
    manifest = {}
    for rel, content in changes.items():
        target = root / rel
        previous = target.read_bytes() if target.exists() else None
        if previous is not None:
            destination = backup / rel
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            destination.write_bytes(previous)
            destination.chmod(0o600)
        metadata = target.stat() if target.exists() else target.parent.stat()
        manifest[rel] = {
            "uid": metadata.st_uid, "gid": metadata.st_gid,
            "mode": metadata.st_mode & 0o777,
            "existed": previous is not None,
            "before_sha256": hashlib.sha256(previous).hexdigest() if previous is not None else None,
            "after_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (backup / "manifest.json").chmod(0o600)
    # Validate every source and save every original before the first mutation.
    for rel, content in changes.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".gpm-crew-pending")
        temporary.write_text(content, encoding="utf-8")
        temporary.chmod(target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.chown(str(temporary), manifest[rel]["uid"], manifest[rel]["gid"])
        os.replace(str(temporary), str(target))
    print(json.dumps({"written_files": len(changes), "backup_retained": True}))


if __name__ == "__main__":
    main()
