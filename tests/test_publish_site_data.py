import subprocess

from scripts import publish_site_data_main as publisher


def test_large_site_data_uses_git_transport(tmp_path, monkeypatch):
    small = tmp_path / "small.json"
    large = tmp_path / "large.json"
    small.write_bytes(b"1234")
    large.write_bytes(b"12345678901")
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "GIT_TRANSPORT_THRESHOLD", 10)

    assert publisher._needs_git_transport([("small.json", "data/small.json")]) is False
    assert publisher._needs_git_transport([("large.json", "data/large.json")]) is True


def test_git_clone_retries_after_transient_failure(tmp_path, monkeypatch):
    calls = []

    def fake_run_git(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(128, ["git", *args])
        return subprocess.CompletedProcess(["git", *args], 0)

    monkeypatch.setattr(publisher, "_run_git", fake_run_git)
    monkeypatch.setattr(publisher.time, "sleep", lambda _: None)

    checkout = publisher._clone_with_retry("https://example.test/repo.git", "gh-pages", tmp_path)

    assert checkout == tmp_path / "repo-2"
    assert len(calls) == 2


def test_cached_publish_pushes_even_when_files_are_already_staged(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    calls = []

    def fake_run_git(*args, **kwargs):
        calls.append(args)
        stdout = "" if args[:2] == ("status", "--porcelain") else "abc123\n"
        return subprocess.CompletedProcess(["git", *args], 0, stdout=stdout)

    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "_run_git", fake_run_git)

    publisher._publish_from_checkout(
        checkout,
        "gh-pages",
        [("source.json", "v2/data/app-data.json")],
        "Update data",
    )

    assert (checkout / "v2" / "data" / "app-data.json").read_text(encoding="utf-8") == "{}"
    assert ("push", "origin", "gh-pages") in calls
    assert not any(call and call[0] == "commit" for call in calls)


def test_expand_directory_mappings_excludes_monolith(tmp_path, monkeypatch):
    data = tmp_path / "site-v2" / "data"
    data.mkdir(parents=True)
    (tmp_path / "site-v2" / "index.html").write_text("site", encoding="utf-8")
    (data / "manifest.json").write_text("{}", encoding="utf-8")
    (data / "app-data.json").write_text("legacy", encoding="utf-8")
    monkeypatch.setattr(publisher, "ROOT", tmp_path)

    files, roots = publisher._expand_directory_mappings(
        ["site-v2=v2"], ["site-v2/data/app-data.json"]
    )

    assert roots == ["v2"]
    assert ("site-v2/index.html", "v2/index.html") in files
    assert ("site-v2/data/manifest.json", "v2/data/manifest.json") in files
    assert all("app-data.json" not in source for source, _ in files)


def test_sync_root_removes_stale_files_before_copy(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    (checkout / "v2" / "data").mkdir(parents=True)
    (checkout / "v2" / "data" / "app-data.json").write_text("stale", encoding="utf-8")
    source = tmp_path / "manifest.json"
    source.write_text("{}", encoding="utf-8")
    calls = []

    def fake_run_git(*args, **kwargs):
        calls.append(args)
        stdout = " M v2/data/manifest.json\n" if args[:2] == ("status", "--porcelain") else "abc123\n"
        return subprocess.CompletedProcess(["git", *args], 0, stdout=stdout)

    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "_run_git", fake_run_git)

    publisher._publish_from_checkout(
        checkout,
        "gh-pages",
        [("manifest.json", "v2/data/manifest.json")],
        "Deploy shards",
        sync_roots=["v2"],
    )

    assert not (checkout / "v2" / "data" / "app-data.json").exists()
    assert (checkout / "v2" / "data" / "manifest.json").is_file()
    assert ("add", "-A", "--", "v2", "v2/data/manifest.json") in calls
