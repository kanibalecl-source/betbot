from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_uses_dedicated_dockerfile_and_healthcheck():
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    railway = (ROOT / "railway-api.toml").read_text(encoding="utf-8")

    assert 'CMD ["sh", "scripts/start_fastapi.sh"]' in dockerfile
    assert 'dockerfilePath = "Dockerfile.api"' in railway
    assert 'healthcheckPath = "/api/v1/health"' in railway


def test_api_start_is_safe_by_default():
    script = (ROOT / "scripts" / "start_fastapi.sh").read_text(encoding="utf-8")

    assert ': "${BETTING_ENABLED:=false}"' in script
    assert ': "${REALTIME_ENABLED:=false}"' in script
    assert "app.main:app" in script
    assert "--reload" not in script


def test_realtime_is_disabled_in_default_configuration():
    config = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    routes = (ROOT / "app" / "realtime" / "routes.py").read_text(encoding="utf-8")

    assert "realtime_enabled: bool = False" in config
    assert 'APIRouter(prefix="/realtime"' in routes


def test_main_service_start_files_are_not_replaced():
    procfile = (ROOT / "Procfile").read_text(encoding="utf-8")
    start_script = (ROOT / "start.sh").read_text(encoding="utf-8")

    assert "app_launcher.py" in procfile
    assert "streamlit run dashboard_streamlit.py" in start_script
