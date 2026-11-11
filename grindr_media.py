#!/usr/bin/env python3
"""Ingest bytes already obtained by supported browser tools. Never downloads URLs."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit, urlunsplit


PROVIDERS = {"browser-page-assets", "browser-download"}


def redacted_url(value):
    p = urlsplit(value or "")
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("A credential-free browser-observed HTTP(S) resource is required")
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def media_type(path):
    with Path(path).open("rb") as stream:
        head = stream.read(32)
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg", ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png", ".png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image", "image/gif", ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image", "image/webp", ".webp"
    if head[4:8] == b"ftyp":
        return "video", "video/mp4", ".mp4"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video", "video/webm", ".webm"
    if head.startswith(b"OggS"):
        return "audio", "audio/ogg", ".ogg"
    if head.startswith(b"ID3") or head[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "audio", "audio/mpeg", ".mp3"
    raise ValueError("Downloaded artifact is not recognized media; no HTML/login/screenshot substitute")


def acquisition_scope(archive_dir):
    raw = archive_member(archive_dir, "raw/dom_snapshots.json")
    raw_bytes = raw.read_bytes()
    data = json.loads(raw_bytes)
    refs = set()
    for snapshot in data.get("snapshots", []):
        for child in snapshot.get("children", []):
            for field, kind in (("images", "image"), ("videos", "video"), ("audios", "audio")):
                for item in child.get(field, []):
                    src = item.get("src") or item.get("urlRedacted")
                    if not src or "twemoji" in item.get("className", ""):
                        continue
                    url = redacted_url(src)
                    if "/images/profile/" not in url:
                        refs.add((url, kind))
    return hashlib.sha256(raw_bytes).hexdigest(), refs


def archive_member(archive_dir, relative):
    root = Path(archive_dir).resolve()
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Invalid archive path")
    candidate = root
    for component in relative.parts:
        try:
            info = candidate.stat()
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise PermissionError("Archive directories must be owner-controlled")
        candidate /= component
        if candidate.is_symlink():
            raise ValueError("Archive path must not contain a symlink")
    return candidate


def local_media_path(archive_dir, relative):
    if not isinstance(relative, str) or "\\" in relative or any(ord(c) < 32 for c in relative):
        raise ValueError("Invalid media path")
    path = Path(relative)
    if path.parts[:1] != ("media",) or len(path.parts) < 2 or path.as_posix() != relative:
        raise ValueError("Media path must remain in this archive's media directory")
    return archive_member(archive_dir, path)


def verify_record(archive_dir, record):
    path = local_media_path(archive_dir, record["local_path"])
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("Saved media is missing or empty")
    if path.stat().st_size != record["bytes"] or digest_file(path) != record["sha256"]:
        raise ValueError("Saved media byte count or SHA256 mismatch")
    kind, mime, _ = media_type(path)
    if record.get("kind", kind) != kind or record.get("contentType", mime) != mime:
        raise ValueError("Saved media type mismatch")
    if record["urlRedacted"] != redacted_url(record["urlRedacted"]):
        raise ValueError("Signed or fragment-bearing URL must not be persisted")
    return record


def load_verified_map(archive_dir):
    path = archive_member(archive_dir, "raw/media_copy_summary.json")
    if not path.exists():
        return {}
    summary = json.loads(path.read_text(encoding="utf-8"))
    scope, refs = acquisition_scope(archive_dir)
    if summary.get("acquisitionSha256", scope) != scope:
        raise ValueError("Media manifest belongs to a different acquisition")
    result = {}
    for record in summary.get("copied", []):
        verify_record(archive_dir, record)
        kind = record.get("kind", media_type(local_media_path(archive_dir, record["local_path"]))[0])
        if (record["urlRedacted"], kind) not in refs:
            raise ValueError("Media has no matching reference in this chat acquisition")
        key = (record["urlRedacted"], kind)
        if key in result and result[key] != record:
            raise ValueError("Conflicting records for one media reference")
        result[key] = record
    return result


@contextmanager
def manifest_lock(archive_dir):
    lock = archive_member(archive_dir, "raw/.media-ingest.lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise PermissionError("Archive lock must be an owned regular file")
        os.fchmod(fd, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


@contextmanager
def private_output(path):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".archive-output-")
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_private_text(path, value):
    with private_output(path) as stream:
        stream.write(value)


def atomic_manifest(path, data):
    with private_output(path) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def ingest(archive_dir, source, url, kind, provider):
    archive_dir = Path(archive_dir)
    if provider not in PROVIDERS:
        raise ValueError("Only supported browser downloads/page assets are accepted")
    if url != redacted_url(url):
        raise ValueError("Pass only a redacted URL; never pass signed URLs in argv/metadata")
    scope, refs = acquisition_scope(archive_dir)
    if (url, kind) not in refs:
        raise ValueError("Resource is not referenced by this chat acquisition")
    source = Path(source)
    actual_kind, mime, suffix = media_type(source)
    if actual_kind != kind:
        raise ValueError("Downloaded media kind does not match its observed reference")
    sha = digest_file(source)
    size = source.stat().st_size
    if not size:
        raise ValueError("Empty media artifact")
    with manifest_lock(archive_dir):
        if acquisition_scope(archive_dir)[0] != scope:
            raise ValueError("Acquisition changed while preparing media; retry only after finalization")
        manifest = archive_member(archive_dir, "raw/media_copy_summary.json")
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("acquisitionSha256") != scope:
                raise ValueError("Immutable acquisition changed; cannot merge media across chats")
        else:
            data = {"schemaVersion": 1, "acquisitionSha256": scope, "copied": []}
        existing = None
        for record in data["copied"]:
            if record["urlRedacted"] != url:
                continue
            previous_kind = record.get("kind")
            if previous_kind is None:
                previous_kind = media_type(local_media_path(archive_dir, record["local_path"]))[0]
            if previous_kind == kind:
                existing = record
                break
        if existing:
            verify_record(archive_dir, existing)
            if existing["sha256"] != sha:
                raise ValueError("Resource changed; preserve the prior capture instead of overwriting")
            return existing
        relative = f"media/objects/{sha}{suffix}"
        destination = local_media_path(archive_dir, relative)
        (archive_dir / "media").mkdir(exist_ok=True, mode=0o700)
        destination.parent.mkdir(exist_ok=True, mode=0o700)
        if destination.exists():
            if digest_file(destination) != sha:
                raise ValueError("Content-addressed destination is corrupt; not overwritten")
        else:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".media-bytes-", delete=False) as stream:
                temp = Path(stream.name)
            try:
                shutil.copyfile(source, temp)
                os.chmod(temp, 0o600)
                if digest_file(temp) != sha or temp.stat().st_size != size:
                    raise ValueError("Artifact changed during byte-preserving copy")
                with temp.open("rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(temp, destination)
            finally:
                temp.unlink(missing_ok=True)
        record = {"urlRedacted": url, "local_path": relative, "kind": kind,
                  "contentType": mime, "bytes": size, "sha256": sha,
                  "provenance": provider, "representation": "browser-served-bytes",
                  "originalUploadVerified": False, "acquisitionSha256": scope}
        verify_record(archive_dir, record)
        data["copied"].append(record)
        atomic_manifest(manifest, data)
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_dir")
    parser.add_argument("--source-file")
    parser.add_argument("--url-redacted")
    parser.add_argument("--kind", choices=("image", "video", "audio"))
    parser.add_argument("--provider", choices=sorted(PROVIDERS))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify:
            result = {"verifiedMedia": len(load_verified_map(args.archive_dir))}
        else:
            if not all((args.source_file, args.url_redacted, args.kind, args.provider)):
                parser.error("ingest requires source-file, url-redacted, kind and provider")
            record = ingest(args.archive_dir, args.source_file, args.url_redacted, args.kind, args.provider)
            result = {k: record[k] for k in ("local_path", "sha256", "bytes", "kind", "provenance", "representation")}
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        # Never echo unsafe input URLs or source-file contents on failure.
        print(json.dumps({"status": "FAIL", "reason": "media/acquisition validation failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
