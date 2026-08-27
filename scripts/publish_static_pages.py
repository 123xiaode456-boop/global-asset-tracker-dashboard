from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import requests

from publish_site_data_main import publish_files_with_git


OWNER = "123xiaode456-boop"
REPO = "global-asset-tracker-dashboard"
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SITE_V2 = ROOT / "site-v2"
ROOT_FILES = [
    (".nojekyll", SITE / ".nojekyll"),
    ("index.html", SITE / "index.html"),
    ("app.js", SITE / "app.js"),
    ("styles.css", SITE / "styles.css"),
    ("data/app-data.json", SITE / "data" / "app-data.json"),
]


def _files() -> list[tuple[str, Path]]:
    v2_files = [
        ((Path("v2") / source.relative_to(SITE_V2)).as_posix(), source)
        for source in sorted(path for path in SITE_V2.rglob("*") if path.is_file())
        if source != SITE_V2 / "data" / "app-data.json"
    ]
    return [*ROOT_FILES, *v2_files]


def main() -> int:
    files_to_publish = _files()
    files = [(source.relative_to(ROOT).as_posix(), remote_path) for remote_path, source in files_to_publish]
    return publish_files_with_git(
        "gh-pages",
        files,
        "Deploy static global asset dashboard",
        sync_roots=["v2"],
    )

    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    base = f"https://api.github.com/repos/{OWNER}/{REPO}"
    ref_url = f"{base}/git/refs/heads/gh-pages"
    ref_response = session.get(ref_url)
    parent_sha = None
    base_tree = None
    if ref_response.status_code != 404:
        _check(ref_response)
        parent_sha = ref_response.json()["object"]["sha"]
        parent = _check(session.get(f"{base}/git/commits/{parent_sha}"))
        base_tree = parent["tree"]["sha"]

    items = []
    for path, source in files_to_publish:
        raw = source.read_bytes()
        blob = _check(
            session.post(
                f"{base}/git/blobs",
                json={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
            )
        )
        items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"blob: {path} bytes={len(raw)}")

    tree_payload = {"tree": items}
    if base_tree:
        tree_payload["base_tree"] = base_tree
    tree = _check(session.post(f"{base}/git/trees", json=tree_payload))
    commit = _check(
        session.post(
            f"{base}/git/commits",
            json={
                "message": "Deploy static global asset dashboard",
                "tree": tree["sha"],
                "parents": [parent_sha] if parent_sha else [],
            },
        )
    )
    if parent_sha is None:
        _check(session.post(f"{base}/git/refs", json={"ref": "refs/heads/gh-pages", "sha": commit["sha"]}))
        print("created gh-pages")
    else:
        _check(session.patch(ref_url, json={"sha": commit["sha"], "force": False}))
        print("updated gh-pages")
    print(commit["sha"])
    return 0


def _check(response: requests.Response) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error {response.status_code}: {response.text[:1000]}")
    return response.json() if response.text else {}


if __name__ == "__main__":
    raise SystemExit(main())
