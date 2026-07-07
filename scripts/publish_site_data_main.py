from __future__ import annotations

import argparse
import base64
import hashlib
import subprocess
from pathlib import Path

import requests


OWNER = "123xiaode456-boop"
REPO = "global-asset-tracker-dashboard"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = ["site-v2/data/app-data.json"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", default="Update v2 data")
    parser.add_argument("--file", action="append", dest="files")
    args = parser.parse_args()

    files = [_parse_file_mapping(item) for item in (args.files or DEFAULT_FILES)]
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
