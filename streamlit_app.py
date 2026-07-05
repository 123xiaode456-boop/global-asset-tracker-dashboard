from asset_tracker.auth import require_access
from asset_tracker.dashboard import run_app


if require_access():
    run_app()
