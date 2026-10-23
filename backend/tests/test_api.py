from __future__ import annotations


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_catalog_reports_coverage_and_sample_flag(client):
    body = client.get("/api/catalog").json()
    assert body["data_source"] == "sample"
    assert body["is_sample"] is True
    ids = {s["id"] for s in body["series"]}
    assert ids == {"wti", "brent", "henry_hub", "rbob_nyh", "ulsd_nyh"}
    wti = next(s for s in body["series"] if s["id"] == "wti")
    assert wti["first_date"] == "2024-01-01"
    assert wti["observations"] > 600
    assert {sp["id"] for sp in body["spreads"]} == {"brent_wti", "crack_321"}


def test_prices_window_has_warm_moving_averages(client):
    body = client.get("/api/series/wti/prices", params={"start": "2026-06-01"}).json()
    points = body["points"]
    assert body["unit"] == "$/bbl"
    assert points[0]["date"] >= "2026-06-01"
    # Warm-up history means the 50-day MA is populated from the first visible day.
    assert points[0]["ma50"] is not None
    assert points == sorted(points, key=lambda p: p["date"])


def test_unknown_series_404(client):
    assert client.get("/api/series/nope/prices").status_code == 404


def test_summaries(client):
    rows = client.get("/api/summaries").json()
    assert len(rows) == 5
    wti = next(r for r in rows if r["series_id"] == "wti")
    assert wti["low_52w"] <= wti["last"] <= wti["high_52w"]
    assert wti["vol_20d_annualized"] > 0


def test_spreads(client):
    body = client.get("/api/spreads/crack_321", params={"start": "2026-06-01"}).json()
    assert body["unit"] == "$/bbl" and body["window"] == 60
    assert body["points"][0]["zscore"] is not None
    assert client.get("/api/spreads/nope").status_code == 404
    assert client.get("/api/spreads/brent_wti", params={"window": 2}).status_code == 422


def test_pipeline_runs_and_manual_trigger(client):
    assert client.get("/api/pipeline/runs").json()[0]["status"] == "success"
    assert client.post("/api/pipeline/run").status_code == 401
    ok = client.post("/api/pipeline/run", headers={"X-Pipeline-Token": "secret"})
    assert ok.status_code == 200 and ok.json()["status"] == "success"
    assert len(client.get("/api/pipeline/runs").json()) == 2


def test_serves_frontend_when_static_dir_set(tmp_path, sample_source):
    from datetime import date

    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    settings = Settings(
        database_url="sqlite://", history_start=date(2026, 1, 1), static_dir=str(tmp_path)
    )
    with TestClient(create_app(settings, source_factory=lambda: sample_source)) as c:
        assert c.get("/").text == "<div id=root></div>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/favicon.svg").text == "<svg/>"
        assert c.get("/some/client/route").text == "<div id=root></div>"
        assert c.get("/../backend/app/config.py").text == "<div id=root></div>"
        assert c.get("/api/health").json() == {"status": "ok"}
        assert c.get("/api/nope").status_code == 404
