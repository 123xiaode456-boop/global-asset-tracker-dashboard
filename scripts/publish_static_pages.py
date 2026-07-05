from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import requests


OWNER = "123xiaode456-boop"
REPO = "global-asset-tracker-dashboard"
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FILES = [
    ("index.html", SITE / "index.html"),
    ("app.js", SITE / "app.js"),
    ("styles.css", SITE / "styles.css"),
    ("data/app-data.json", SITE / "data" / "app-data.json"),
]


def main() -> int:
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

    items = []
    for path, source in FILES:
        raw = source.read_bytes()
        blob = _check(
            session.post(
                f"{base}/git/blobs",
                json={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
            )
        )
        items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"blob: {path} bytes={len(raw)}")

    tree = _check(session.post(f"{base}/git/trees", json={"tree": items}))
    commit = _check(
        session.post(
            f"{base}/git/commits",
            json={"message": "Deploy static global asset dashboard", "tree": tree["sha"], "parents": []},
        )
    )
    ref_url = f"{base}/git/refs/heads/gh-pages"
    ref_response = session.get(ref_url)
    if ref_response.status_code == 404:
        _check(session.post(f"{base}/git/refs", json={"ref": "refs/heads/gh-pages", "sha": commit["sha"]}))
        print("created gh-pages")
    else:
        _check(ref_response)
        _check(session.patch(ref_url, json={"sha": commit["sha"], "force": True}))
        print("updated gh-pages")
    print(commit["sha"])
    return 0


def _check(response: requests.Response) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error {response.status_code}: {response.text[:1000]}")
    return response.json() if response.text else {}


if __name__ == "__main__":
    raise SystemExit(main())
