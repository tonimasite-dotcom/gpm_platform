"""Deploy only the verified TS adapter, with source/config/assets rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import time

import prepare

ROOT = prepare.ROOT
ASSETS = ("public/dist", "public/mix-manifest.json")
MARKER = "gpm-ts-crew-release-v1"


def run(arguments, owner=None, quiet=False):
    command = (["runuser", "-u", owner, "--"] if owner else []) + arguments
    result = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True)
    if result.returncode:
        # Never print configuration, private source snippets or HTTP responses.
        raise RuntimeError("Command failed: " + " ".join(arguments[:3]))
    return result.stdout


def tree_hash(path):
    digest = hashlib.sha256()
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    for item in files:
        if item.is_symlink():
            raise RuntimeError("Symlink inside a release asset")
        if item.is_file():
            digest.update(str(item.relative_to(path) if path.is_dir() else item.name).encode())
            with item.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def copy_private(source, target):
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    def copy_file(origin, destination):
        shutil.copy2(str(origin), str(destination))
        metadata = Path(origin).stat()
        os.chown(str(destination), metadata.st_uid, metadata.st_gid)
        return str(destination)
    if source.is_dir():
        shutil.copytree(str(source), str(target), copy_function=copy_file)
        for origin in [source] + [p for p in source.rglob("*") if p.is_dir()]:
            destination = target / origin.relative_to(source)
            metadata = origin.stat()
            os.chown(str(destination), metadata.st_uid, metadata.st_gid)
    else:
        copy_file(source, target)


def restore_source(backup):
    if backup.parent != Path("/root") or not backup.name.startswith("gpm-ts-crew-source-"):
        raise RuntimeError("Invalid source rollback directory")
    manifest = json.loads((backup / "manifest.json").read_text())
    allowed = {prepare.SYNC, prepare.FORM, prepare.SERVICE, prepare.BRIGADIER,
               prepare.ROUTES} | set(prepare.PACKAGE_FILES.values())
    if set(manifest) != allowed:
        raise RuntimeError("Unexpected rollback source manifest")
    for rel, metadata in manifest.items():
        target = ROOT / rel
        if metadata["existed"]:
            original = (backup / rel).read_bytes()
            if hashlib.sha256(original).hexdigest() != metadata["before_sha256"]:
                raise RuntimeError("Rollback source hash mismatch")
        elif target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != metadata["after_sha256"]:
            raise RuntimeError("A new adapter file changed since deployment")
    for rel, metadata in manifest.items():
        target = ROOT / rel
        if metadata["existed"]:
            temporary = target.with_name(target.name + ".gpm-crew-restore")
            temporary.write_bytes((backup / rel).read_bytes())
            temporary.chmod(metadata["mode"])
            os.chown(str(temporary), metadata["uid"], metadata["gid"])
            os.replace(str(temporary), str(target))
        elif target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != metadata["after_sha256"]:
                raise RuntimeError("A new adapter file changed since deployment")
            target.unlink()


def rollback(backup):
    if backup.parent != Path("/root") or not backup.name.startswith("gpm-ts-crew-release-"):
        raise RuntimeError("Invalid TS rollback directory")
    receipt = json.loads((backup / "release.json").read_text())
    if receipt.get("marker") != MARKER or receipt.get("root") != str(ROOT):
        raise RuntimeError("Invalid TS rollback receipt")
    owner = receipt["owner"]
    run(["php", "artisan", "down"], owner)
    try:
        restore_source(Path(receipt["source_backup"]))
        for rel in ASSETS:
            saved, target = backup / rel, ROOT / rel
            if tree_hash(saved) != receipt["assets"][rel]:
                raise RuntimeError("Rollback asset hash mismatch")
            if target.is_dir():
                # The exact fixed TS asset path is verified above.
                if target.resolve() != ROOT / rel or rel != "public/dist":
                    raise RuntimeError("Unexpected asset deletion target")
                shutil.rmtree(str(target))
            elif target.exists():
                target.unlink()
            copy_private(saved, target)
        shutil.copy2(str(backup / "runtime-env"), str(ROOT / ".env"))
        run(["php", "artisan", "config:clear"], owner)
        run(["php", "artisan", "route:clear"], owner)
        run(["php", "artisan", "view:clear"], owner)
    finally:
        run(["php", "artisan", "up"], owner)
    print(json.dumps({"rolled_back": True, "crew_data_preserved": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    prepare.verify_root(ROOT)
    if args.rollback:
        rollback(Path(args.rollback))
        return
    if not args.write:
        prepare.build(ROOT, Path(__file__).resolve().parent)
        print(json.dumps({"prepared": True, "write": False}))
        return
    if (ROOT / "storage/framework/down").exists() or (ROOT / "public/build").exists():
        raise RuntimeError("TS is already in maintenance or has a pending asset build")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = Path("/root/gpm-ts-crew-release-" + stamp)
    source_backup = Path("/root/gpm-ts-crew-source-" + stamp)
    backup.mkdir(mode=0o700)
    owner = pwd.getpwuid((ROOT / "package.json").stat().st_uid).pw_name
    receipt = {"marker": MARKER, "root": str(ROOT), "owner": owner,
               "source_backup": str(source_backup), "assets": {}}
    for rel in ASSETS:
        source = ROOT / rel
        receipt["assets"][rel] = tree_hash(source)
        copy_private(source, backup / rel)
        if tree_hash(backup / rel) != receipt["assets"][rel]:
            raise RuntimeError("TS asset backup verification failed")
    copy_private(ROOT / ".env", backup / "runtime-env")
    (backup / "runtime-env").chmod(0o600)
    (backup / "release.json").write_text(json.dumps(receipt, indent=2))
    (backup / "release.json").chmod(0o600)
    run(["php", "artisan", "down"], owner)
    try:
        run(["python3", str(Path(__file__).with_name("prepare.py")),
             "--backup", str(source_backup), "--write"])
        for rel in [prepare.SYNC, prepare.SERVICE, prepare.ROUTES] + [
                p for p in prepare.PACKAGE_FILES.values() if p.endswith(".php")]:
            run(["php", "-l", str(ROOT / rel)])
        run(["php", "artisan", "config:clear"], owner)
        run(["php", "artisan", "route:clear"], owner)
        routes = run(["php", "artisan", "route:list", "--path=logist_orders/gpm_crew"], owner)
        if "gpm_crew" not in routes or "GpmCrewAttendanceController" not in routes:
            raise RuntimeError("TS crew route was not registered")
        run(["npm", "run", "production"], owner)
        manifest = json.loads((ROOT / "public/mix-manifest.json").read_text())
        app_path = ROOT / "public" / manifest["/dist/js/app.js"].lstrip("/")
        if not app_path.is_file() or not str(app_path.resolve()).startswith(str(ROOT / "public/dist") + "/"):
            raise RuntimeError("Unexpected TS bundle target")
        bundle = app_path.read_bytes()
        if "Онлайн-табель GPM".encode() not in bundle:
            raise RuntimeError("Crew panel missing from TS bundle")
        # Verify that server integration credentials did not enter browser JS.
        for line in (ROOT / ".env").read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"APP_KEY", "GPM_APP_API_TOKEN"}:
                value = value.strip().strip(chr(34) + chr(39))
                if len(value) >= 16 and value.encode() in bundle:
                    raise RuntimeError("Server credential detected in browser bundle")
        run(["php", "artisan", "view:clear"], owner)
        receipt.update({"complete": True, "bundle_sha256": hashlib.sha256(bundle).hexdigest()})
        (backup / "release.json").write_text(json.dumps(receipt, indent=2))
        run(["php", "artisan", "up"], owner)
    except Exception:
        rollback(backup)
        raise
    print(json.dumps({"installed": True, "backup": str(backup),
                      "source_backup": str(source_backup),
                      "bundle_sha256": receipt["bundle_sha256"], "flag_unchanged": True}))


if __name__ == "__main__":
    main()
