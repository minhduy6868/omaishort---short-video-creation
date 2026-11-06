from pathlib import Path

from fastapi import FastAPI
from omaishort.d1 import D1Result
from fastapi.testclient import TestClient

from omaishort.desktop import attach_studio, find_app_browser


def test_attach_studio_serves_index_and_keeps_api(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "index.html").write_text("<h1>omaishort</h1>", encoding="utf-8")
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    attach_studio(app, tmp_path)
    client = TestClient(app)
    page = client.get("/")
    asset = client.get("/assets/app.js")
    health_res = client.get("/health")
    assert page.status_code == 200
    assert "omaishort" in page.text
    assert asset.status_code == 200
    assert health_res.json()["status"] == "ok"
    for path in ("/login", "/drama", "/knowledge", "/watch/job123", "/en", "/vi", "/en/studio"):
        screen = client.get(path)
        assert screen.status_code == 200
        assert "omaishort" in screen.text


def test_desktop_window_opens_the_studio_not_the_landing(monkeypatch) -> None:
    import threading

    import uvicorn

    from omaishort import desktop

    opened: list[str] = []

    class InlineThread:
        def __init__(self, target, **_kwargs) -> None:
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(desktop, "attach_studio", lambda *_args: None)
    monkeypatch.setattr(desktop, "_wait_until_up", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(desktop, "open_studio_window", opened.append)
    monkeypatch.setattr(threading, "Thread", InlineThread)
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: None)

    desktop.run()

    assert len(opened) == 1
    assert opened[0].endswith("/work"), "/ redirects to the /vi landing since fix/remake-ui"


def test_d1_result_reads_rows() -> None:
    result = D1Result([{"n": 2}, {"n": 3}])
    assert result.fetchone() == {"n": 2}
    assert result.fetchall() == [{"n": 3}]


def test_sqlite_url_skips_cloud_database(monkeypatch) -> None:
    import omaishort.config as cfg
    from omaishort import db

    monkeypatch.setenv("DATABASE_URL", "sqlite:///C:/tmp/omaishort-test.db")
    monkeypatch.setattr(cfg, "D1_WORKER_URL", "https://omaishort-db.example.workers.dev")
    monkeypatch.setattr(cfg, "D1_WORKER_KEY", "test-key")
    assert db.database_url().startswith("sqlite")
    assert not db.is_d1()


def test_find_app_browser_is_optional() -> None:
    found = find_app_browser()
    assert found is None or Path(found[0]).exists()
