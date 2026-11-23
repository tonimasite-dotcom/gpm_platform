"""Install only the TS test-registration worker adapter. No schema/UI changes."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import time

ROOT = Path("/var/www/gruzpiter/data/www/ts.workstaffcrm.ru")
COMMAND = "app/Console/Commands/SyncGpmAppOrders.php"
FILES = {
    "GpmWorkerMatchPolicy.php": "app/Services/Gpm/GpmWorkerMatchPolicy.php",
    "GpmPreviewWorkerPolicy.php": "app/Services/Gpm/GpmPreviewWorkerPolicy.php",
    "GpmPreviewWorkerSync.php": "app/Services/Gpm/GpmPreviewWorkerSync.php",
}
HOOK = """        $workers = app(\\App\\Services\\Gpm\\GpmPreviewWorkerSync::class)->run();
        $this->info('Preview workers linked: ' . $workers['linked'] . '; deferred: ' . $workers['deferred']);
"""
ANCHOR = "        if (!$sync->enabled()) {"


def fingerprint(content):
    return hashlib.sha256(content).hexdigest()


def identity():
    if ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError("Only the verified TS root is supported")
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip().strip(chr(34)+chr(39))
    if values.get("APP_URL", "").rstrip("/") != "https://ts.workstaffcrm.ru":
        raise RuntimeError("TS application identity mismatch")
    import re
    if not re.search(r"(^|[_-])(test|ts|demo)([_-]|$)", values.get("DB_DATABASE", ""), re.I):
        raise RuntimeError("A separate TS test database is required")


def command(arguments, owner=None):
    prefix = ["runuser", "-u", owner, "--"] if owner else []
    result = subprocess.run(prefix + arguments, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True)
    if result.returncode:
        raise RuntimeError("TS verification command failed: " + " ".join(arguments[:3]))
    return result.stdout


def patched(text):
    if HOOK in text:
        return text
    if text.count(ANCHOR) != 1:
        raise RuntimeError("Unsupported TS synchronization command")
    return text.replace(ANCHOR, HOOK + ANCHOR)


def write_file(path, content, metadata):
    if path.is_symlink() or path.parent.is_symlink() or not str(path.resolve()).startswith(str(ROOT) + "/"):
        raise RuntimeError("Target escapes TS")
    if not path.parent.exists():
        path.parent.mkdir(mode=0o755)
        os.chown(str(path.parent), metadata["uid"], metadata["gid"])
    temporary = path.with_name(path.name+".gpm-preview-pending")
    temporary.write_bytes(content)
    temporary.chmod(metadata["mode"])
    os.chown(str(temporary), metadata["uid"], metadata["gid"])
    os.replace(str(temporary), str(path))


def settings(enabled, since=None):
    path = ROOT/".env"
    text = path.read_text()
    keys = {"GPM_PREVIEW_WORKER_SYNC_ENABLED": "true" if enabled else "false"}
    if since is not None:
        keys["GPM_PREVIEW_WORKER_SYNC_SINCE"] = str(since)
    lines = [line for line in text.splitlines() if not any(line.startswith(key+"=") for key in keys)]
    lines.extend(key+"="+value for key,value in keys.items())
    stat = path.stat()
    write_file(path, ("\n".join(lines)+"\n").encode(),
               {"uid":stat.st_uid,"gid":stat.st_gid,"mode":stat.st_mode & 0o777})


def load_backup(path):
    if path.parent != Path("/root") or not path.name.startswith("gpm-ts-preview-workers-"):
        raise RuntimeError("Invalid TS adapter backup")
    record = json.loads((path/"manifest.json").read_text())
    if record["root"] != str(ROOT):
        raise RuntimeError("Backup identity mismatch")
    return record


def restore(backup):
    record = load_backup(backup)
    expected = record.get("env_after")
    actual = fingerprint((ROOT/".env").read_bytes())
    if actual not in {record["env_before"], expected}:
        def unrelated(content):
            return [line for line in content.splitlines() if not line.startswith(
                ("GPM_PREVIEW_WORKER_SYNC_ENABLED=", "GPM_PREVIEW_WORKER_SYNC_SINCE="))]
        if unrelated((ROOT/".env").read_text()) != unrelated((backup/"runtime-env").read_text()):
            raise RuntimeError("TS settings changed after installation; review before rollback")
    for relative, metadata in record["files"].items():
        target = ROOT/relative
        if metadata["existed"]:
            original = (backup/relative).read_bytes()
            if fingerprint(original) != metadata["before"]:
                raise RuntimeError("Backup verification failed")
        elif target.exists() and fingerprint(target.read_bytes()) != metadata["after"]:
            raise RuntimeError("A new adapter file changed after installation")
    settings(False)
    command(["php","artisan","config:clear"], record["owner"])
    directory = ROOT/"storage/app/gpm-preview-worker-links"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (directory/"sync.lock").open("a+") as lock:
        (directory/"sync.lock").chmod(0o600)
        os.chown(str(directory/"sync.lock"), record["env_metadata"]["uid"], record["env_metadata"]["gid"])
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            for relative, metadata in record["files"].items():
                target = ROOT/relative
                if metadata["existed"]:
                    write_file(target, (backup/relative).read_bytes(), metadata)
                elif target.exists():
                    target.unlink()
            write_file(ROOT/".env", (backup/"runtime-env").read_bytes(), record["env_metadata"])
            command(["php","artisan","config:clear"], record["owner"])
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    print(json.dumps({"rolled_back":True,"test_workers_and_receipts_preserved":True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--rollback")
    parser.add_argument("--enable")
    args = parser.parse_args()
    identity()
    if args.rollback:
        restore(Path(args.rollback))
        return
    if args.enable:
        backup = Path(args.enable)
        record = load_backup(backup)
        for relative, metadata in record["files"].items():
            if fingerprint((ROOT/relative).read_bytes()) != metadata["after"]:
                raise RuntimeError("TS adapter changed before enabling")
        settings(True)
        command(["php","artisan","config:clear"], record["owner"])
        record["env_after"] = fingerprint((ROOT/".env").read_bytes())
        (backup/"manifest.json").write_text(json.dumps(record, indent=2))
        print(json.dumps({"enabled":True,"test_only":True}))
        return
    original = (ROOT/COMMAND).read_text()
    if HOOK in original:
        raise RuntimeError("Adapter is already installed; use its existing receipt")
    sources = {relative: (Path(__file__).parent/name).read_bytes() for name,relative in FILES.items()}
    sources[COMMAND] = patched(original).encode()
    for relative in FILES.values():
        if (ROOT/relative).exists():
            raise RuntimeError("New adapter target already exists")
    if not args.write:
        print(json.dumps({"prepared_files":len(sources),"write":False,"ui_changed":False}))
        return
    if not args.backup:
        raise RuntimeError("A private TS backup path is required")
    backup = Path(args.backup)
    if backup.parent != Path("/root") or not backup.name.startswith("gpm-ts-preview-workers-") or backup.exists():
        raise RuntimeError("A new private backup path is required")
    backup.mkdir(mode=0o700)
    stat = (ROOT/COMMAND).stat()
    owner = pwd.getpwuid(stat.st_uid).pw_name
    default = {"uid":stat.st_uid,"gid":stat.st_gid,"mode":0o644}
    record = {"root":str(ROOT),"owner":owner,"files":{},"since":time.time()}
    for relative, content in sources.items():
        target = ROOT/relative
        existed = target.exists()
        metadata = target.stat() if existed else stat
        entry = {"uid":metadata.st_uid,"gid":metadata.st_gid,
                 "mode":metadata.st_mode & 0o777 if existed else 0o644,
                 "existed":existed,"before":None,"after":fingerprint(content)}
        if existed:
            data = target.read_bytes()
            entry["before"] = fingerprint(data)
            saved = backup/relative
            saved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            saved.write_bytes(data);saved.chmod(0o600)
        record["files"][relative] = entry
    env = ROOT/".env"; data=env.read_bytes(); stat=env.stat()
    record["env_before"] = fingerprint(data)
    record["env_metadata"] = {"uid":stat.st_uid,"gid":stat.st_gid,"mode":stat.st_mode & 0o777}
    (backup/"runtime-env").write_bytes(data);(backup/"runtime-env").chmod(0o600)
    (backup/"manifest.json").write_text(json.dumps(record,indent=2));(backup/"manifest.json").chmod(0o600)
    try:
        # New classes precede the console hook; disabled by default during installation.
        for relative, content in sources.items():
            write_file(ROOT/relative, content, record["files"][relative])
            command(["php","-l",str(ROOT/relative)])
        cache = ROOT/"storage/app/gpm-preview-worker-links"
        if cache.is_symlink() or not str(cache.resolve()).startswith(str(ROOT)+"/"):
            raise RuntimeError("Unsafe TS test worker cache")
        cache.mkdir(mode=0o700, exist_ok=True)
        cache.chmod(0o700)
        lock = cache/"sync.lock"
        if lock.is_symlink():
            raise RuntimeError("Unsafe TS test worker lock")
        lock.touch(exist_ok=True)
        lock.chmod(0o600)
        os.chown(str(lock),default["uid"],default["gid"])
        os.chown(str(cache),default["uid"],default["gid"])
        settings(False, record["since"])
        command(["php","artisan","config:clear"], owner)
        record["env_after"] = fingerprint((ROOT/".env").read_bytes())
        (backup/"manifest.json").write_text(json.dumps(record,indent=2))
    except Exception:
        restore(backup)
        raise
    print(json.dumps({"installed":True,"enabled":False,"backup":str(backup),
                      "new_tables":0,"ui_changed":False,"since":record["since"]}))


if __name__ == "__main__":
    main()
