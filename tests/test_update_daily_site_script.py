from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_update_daily_site_fetches_futures_prices_before_static_export():
    script = (PROJECT_ROOT / "scripts" / "update_daily_site.ps1").read_text(encoding="utf-8")

    fetch_index = script.index("fetch-prices")
    export_index = script.index("export_static_site.py")

    assert fetch_index < export_index
    assert "--dataset-type\", \"core\"" in script
    assert "--asset-kind\", \"domestic-futures\"" in script
    assert "--missing-only" in script
