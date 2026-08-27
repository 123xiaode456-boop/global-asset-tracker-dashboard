from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests


OWNER = "123xiaode456-boop"
REPO = "global-asset-tracker-dashboard"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = ["site-v2/data/app-data.json"]
GIT_TRANSPORT_THRESHOLD = 20 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", default="Update v2 data")
    parser.add_argument("--file", action="append", dest="files")
    parser.add_argument("--directory", action="append", dest="directories")
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    raw_files = args.files or ([] if args.directories else DEFAULT_FILES)
    files = [_parse_file_mapping(item) for item in raw_files]
    directory_files, sync_roots = _expand_directory_mappings(args.directories or [], args.exclude)
    files.extend(directory_files)
    if sync_roots or _needs_git_transport(files):
        return publish_files_with_git(args.branch, files, args.message, sync_roots=sync_roots)

    token = subprocess.check_output([_gh_path(), "auth", "token"], text=True).strip()
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    base = f"https://api.github.com/repos/{OWNER}/{REPO}"
    ref = _check(session.get(f"{base}/git/ref/heads/{args.branch}", timeout=60))
    parent_sha = ref["object"]["sha"]
    parent = _check(session.get(f"{base}/git/commits/{parent_sha}", timeout=60))
    base_tree = parent["tree"]["sha"]

    items = []
    for source_rel, remote_path in files:
        source = ROOT / source_rel
        raw = source.read_bytes()
        local_sha = _git_blob_sha(raw)
        remote_sha = _remote_blob_sha(session, base, remote_path, args.branch)
        if remote_sha == local_sha:
            print(f"unchanged: {source_rel} -> {remote_path}")
            continue

        blob = _check(
            session.post(
                f"{base}/git/blobs",
                json={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
                timeout=180,
            )
        )
        items.append({"path": remote_path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"blob: {source_rel} -> {remote_path} bytes={len(raw)} sha={blob['sha']}")

    if not items:
        print("no changes to publish")
        return 0

    tree = _check(
        session.post(
            f"{base}/git/trees",
            json={"base_tree": base_tree, "tree": items},
            timeout=60,
        )
    )
    commit = _check(
        session.post(
            f"{base}/git/commits",
            json={"message": args.message, "tree": tree["sha"], "parents": [parent_sha]},
            timeout=60,
        )
    )
    _check(
        session.patch(
            f"{base}/git/refs/heads/{args.branch}",
            json={"sha": commit["sha"], "force": False},
            timeout=60,
        )
    )
    print(f"updated {args.branch} {parent_sha} -> {commit['sha']}")
    return 0


def _needs_git_transport(files: list[tuple[str, str]]) -> bool:
    return any((ROOT / source_rel).stat().st_size > GIT_TRANSPORT_THRESHOLD for source_rel, _ in files)


def publish_files_with_git(
    branch: str,
    files: list[tuple[str, str]],
    message: str,
    sync_roots: list[str] | None = None,
) -> int:
    remote = f"https://github.com/{OWNER}/{REPO}.git"
    cached_checkout = ROOT / "data" / "publish-cache" / branch
    if (cached_checkout / ".git").exists():
        _sync_cached_checkout(cached_checkout, branch)
        return _publish_from_checkout(cached_checkout, branch, files, message, sync_roots=sync_roots)

    with tempfile.TemporaryDirectory(prefix="global-asset-dashboard-publish-") as temp_dir:
        checkout = _clone_with_retry(remote, branch, Path(temp_dir))
        return _publish_from_checkout(checkout, branch, files, message, sync_roots=sync_roots)


def _sync_cached_checkout(checkout: Path, branch: str) -> None:
    _run_git("checkout", branch, cwd=checkout)
    try:
        _run_git("fetch", "origin", branch, cwd=checkout)
        _run_git("merge", "--ff-only", f"origin/{branch}", cwd=checkout)
    except subprocess.CalledProcessError:
        print("cached checkout refresh failed; continuing with the last local checkpoint")


def _publish_from_checkout(
    checkout: Path,
    branch: str,
    files: list[tuple[str, str]],
    message: str,
    sync_roots: list[str] | None = None,
) -> int:
    _run_git("config", "user.name", OWNER, cwd=checkout)
    _run_git("config", "user.email", f"{OWNER}@users.noreply.github.com", cwd=checkout)

    remote_paths = []
    checked_root = checkout.resolve()
    for remote_root in sync_roots or []:
        if not remote_root or remote_root in {".", "/"}:
            raise ValueError(f"Refusing to sync unsafe remote directory: {remote_root!r}")
        destination_root = (checkout / remote_root).resolve()
        if destination_root == checked_root or checked_root not in destination_root.parents:
            raise ValueError(f"Remote directory escapes checkout: {remote_root}")
        if destination_root.exists():
            shutil.rmtree(destination_root)
        remote_paths.append(remote_root)
    for source_rel, remote_path in files:
        source = ROOT / source_rel
        destination = checkout / remote_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        remote_paths.append(remote_path)
        print(f"stage: {source_rel} -> {remote_path} bytes={source.stat().st_size}")

    _run_git("add", "-A", "--", *dict.fromkeys(remote_paths), cwd=checkout)
    status = _run_git("status", "--porcelain", cwd=checkout, capture=True).stdout.strip()
    if status:
        _run_git("commit", "-m", message, cwd=checkout)
    else:
        print("no file changes; checking whether a previous commit still needs pushing")
    _run_git("push", "origin", branch, cwd=checkout)
    commit = _run_git("rev-parse", "HEAD", cwd=checkout, capture=True).stdout.strip()
    print(f"updated {branch} via git transport: {commit}")
    return 0


def _clone_with_retry(remote: str, branch: str, temp_root: Path, attempts: int = 3) -> Path:
    for attempt in range(1, attempts + 1):
        checkout = temp_root / f"repo-{attempt}"
        try:
            _run_git("clone", "--depth", "1", "--branch", branch, remote, str(checkout))
            return checkout
        except subprocess.CalledProcessError:
            if attempt == attempts:
                raise
            print(f"git clone attempt {attempt} failed; retrying")
            time.sleep(attempt * 2)
    raise RuntimeError("git clone retry loop ended unexpectedly")


def _run_git(*args: str, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )


def _gh_path() -> str:
    fixed = Path(r"C:\Program Files\GitHub CLI\gh.exe")
    return str(fixed) if fixed.exists() else "gh"


def _parse_file_mapping(value: str) -> tuple[str, str]:
    if "=" not in value:
        return value, value
    source, remote_path = value.split("=", 1)
    if not source or not remote_path:
        raise ValueError(f"Invalid file mapping: {value}")
    return source, remote_path


def _expand_directory_mappings(
    values: list[str],
    excludes: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    files: list[tuple[str, str]] = []
    sync_roots: list[str] = []
    for value in values:
        source_rel, remote_root = _parse_file_mapping(value)
        source_dir = ROOT / source_rel
        if not source_dir.is_dir():
            raise ValueError(f"Directory mapping source does not exist: {source_rel}")
        sync_roots.append(remote_root.rstrip("/"))
        for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            source_item = source.relative_to(ROOT).as_posix()
            if any(fnmatch.fnmatch(source_item, pattern) for pattern in excludes):
                continue
            remote_item = (Path(remote_root) / source.relative_to(source_dir)).as_posix()
            files.append((source_item, remote_item))
    return files, list(dict.fromkeys(sync_roots))


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _remote_blob_sha(session: requests.Session, base: str, rel: str, branch: str) -> str | None:
    response = session.get(f"{base}/contents/{rel}", params={"ref": branch}, timeout=60)
    if response.status_code == 404:
        return None
    _check(response)
    return response.json().get("sha")


def _check(response: requests.Response) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error {response.status_code}: {response.text[:1000]}")
    return response.json() if response.text else {}


if __name__ == "__main__":
    raise SystemExit(main())
