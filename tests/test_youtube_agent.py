import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from cliper.youtube_agent import (
    score_hook,
    score_hooks,
    lint_title_and_thumb,
    lint_titles,
    detect_deadair,
    generate_youtube_chapters,
    parse_retention_csv,
    analyze_swipe_outliers,
    get_voice_profile,
    save_voice_profile,
    load_formulas,
)
from cliper.editorial import choose_hook, attention_report
from cliper.config import Config
from cliper.web import create_app


def test_score_hook_strong_formula():
    text = "You won't believe why 97% of creators quit before video 30. Here is what you must do."
    result = score_hook(text)
    assert result["verdict"] >= 65
    assert result["band"] in ("STRONG", "WORKABLE")
    assert result["formula"] != "NO_FORMULA_MATCH"
    assert "SPECIFICITY" in result["properties"]
    assert "BREVITY" in result["properties"]
    assert result["weakest"] in result["properties"]
    assert len(result["fix"]) > 0


def test_score_hook_weak():
    text = "Hey guys, welcome back to the channel, today I am just going to talk about stuff."
    result = score_hook(text)
    assert result["verdict"] < 55
    assert result["band"] == "WEAK"
    assert result["properties"]["STAKES"] < 50 or result["properties"]["BREVITY"] < 50


def test_score_hooks_ranking():
    candidates = [
        "Hey guys what is up welcome back.",
        "You won't believe why 97% of creators quit before video 30. Here is what you must do.",
        "Never buy this camera in 2026.",
    ]
    ranked = score_hooks(candidates)
    assert len(ranked) == 3
    # Top ranked should have highest verdict
    assert ranked[0]["verdict"] >= ranked[1]["verdict"] >= ranked[2]["verdict"]
    assert ranked[0]["hook"] != "Hey guys what is up welcome back."


def test_lint_title_and_thumb_desktop_mobile_limits():
    # Long title exceeding 60 characters
    long_title = "THIS IS A VERY LONG TITLE THAT WILL DEFINITELY BE CUT OFF ON YOUTUBE SEARCH AND MOBILE"
    res = lint_title_and_thumb(long_title, thumb="VERY LONG")
    assert res["status"] in ("WARN", "FAIL")
    assert len(res["desktop_preview"]) > 0
    assert len(res["mobile_preview"]) > 0
    # Should catch shouting
    assert any(i["kind"] == "shouting" for i in res["issues"])
    # Should catch duplication
    assert any(i["kind"] == "duplicate" for i in res["issues"])


def test_lint_title_and_thumb_clean():
    clean_title = "Why 99% of Startups Fail in Month 3"
    res = lint_title_and_thumb(clean_title, thumb="THE TRUTH")
    assert res["status"] == "PASS"
    assert res["score"] >= 80
    assert len(res["issues"]) == 0
    assert len(res["good"]) >= 2


def test_detect_deadair_gaps_and_fillers():
    srt_content = """1
00:00:00,000 --> 00:00:01,000
Um.

2
00:00:03,500 --> 00:00:05,000
I wanted to show the first screen.

3
00:00:05,200 --> 00:00:07,000
I wanted to show the second screen.
"""
    result = detect_deadair(srt_content, floor=1.5)
    assert len(result["cuts"]) > 0
    kinds = [c["kind"] for c in result["cuts"]]
    # Gap between 00:00:01 and 00:00:03,500 is 2.5s > 1.5s floor -> DEAD
    assert "DEAD" in kinds
    # Um. cue is pure filler -> FILLER
    assert "FILLER" in kinds
    # Retake restart -> REPEAT
    assert "REPEAT" in kinds


def test_generate_youtube_chapters_compliance():
    srt_content = """1
00:00:00,000 --> 00:00:15,000
Introduction to high retention editing and hook design.

2
00:00:15,000 --> 00:00:35,000
Deep dive into audience retention curves and cliff drops.

3
00:00:35,000 --> 00:00:55,000
Final takeaways on publishing workflow and conclusion.

4
00:00:55,000 --> 00:01:15,000
Summary of key steps and end screen actions.
"""
    result = generate_youtube_chapters(srt_content, target=3)
    assert result["valid"] is True
    assert len(result["chapters"]) >= 3
    # Rule 1: First chapter starts at 00:00
    assert result["chapters"][0]["label"] == "0:00" or result["chapters"][0]["start"] == 0.0
    # Rule 2: Minimum 3 chapters
    assert len(result["chapters"]) >= 3
    # Rule 3: Formatted text output
    assert "0:00" in result["formatted_text"]


def test_parse_retention_csv_diagnostics():
    csv_data = """0,100
10,85
20,70
30,60
60,55
90,50
120,30
150,28
"""
    result = parse_retention_csv(csv_data, duration=150)
    # Hook leak in first 30 seconds: 100% -> 60% = 40% drop
    assert result["hook_leak"] >= 35.0
    assert result["hook_verdict"] in ("leaking", "severe")
    # Cliff drop at 90s -> 120s (50% -> 30% = 20% drop > 5%)
    assert len(result["cliffs"]) >= 1
    assert result["cliffs"][0]["lost"] >= 15.0
    assert result["slide_rate"] > 0


def test_analyze_swipe_outliers_calculation():
    videos = [
        {"channel": "TechGuy", "title": "My setup tour", "views": 10000},
        {"channel": "TechGuy", "title": "Why I switched laptops", "views": 12000},
        {"channel": "TechGuy", "title": "Don't buy an M3 Mac in 2026", "views": 45000},
        {"channel": "TechGuy", "title": "Best mouse for coding", "views": 9000},
        {"channel": "OtherChannel", "title": "Regular vlog", "views": 50000},
    ]
    result = analyze_swipe_outliers(videos, min_multiple=2.0)
    assert len(result["outliers"]) >= 1
    top = result["outliers"][0]
    assert top["channel"] == "TechGuy"
    assert "Mac" in top["title"]
    assert top["multiple"] >= 3.0


def test_voice_profile_roundtrip(tmp_path, monkeypatch):
    test_voice_file = tmp_path / "voice.md"
    monkeypatch.setattr("cliper.youtube_agent.LOCAL_VOICE", test_voice_file)
    test_content = "# Creator Voice\n\nI speak directly and avoid generic buzzwords.\n"
    save_voice_profile(test_content)
    loaded = get_voice_profile()
    assert "avoid generic buzzwords" in loaded


def test_editorial_choose_hook_with_yt_agent(transcript):
    title = "Why did my first project fail?"
    variants = [
        "Hey everyone welcome back.",
        "Why 97% of startups fail before day 30.",
        "Check the soil before watering again.",
    ]
    source = "Why 97% of startups fail before day 30: they build before testing demand."
    best, top3 = choose_hook(title, variants, source)
    assert best in [title, *variants]
    # Should select the 97% startup hook because it matches source numbers and scores high
    assert "97%" in best


def test_web_api_yt_endpoints(cfg):
    app = create_app(cfg, start_engine=False, token="test-key", project_root=cfg.data_dir)
    with TestClient(app) as client:
        # Establish session
        r_sess = client.post("/api/session", json={"key": "test-key"})
        assert r_sess.status_code == 200
        client.headers["X-CSRF-Token"] = r_sess.json()["csrf"]

        # 1. Status
        r = client.get("/api/yt/status")
        assert r.status_code == 200
        data = r.json()
        assert data["skills_count"] == 11
        assert data["status"] == "active"

        # 2. Hookscore
        r = client.post("/api/yt/hookscore", json={"hook": "97% of creators quit before video 30."})
        assert r.status_code == 200
        assert "verdict" in r.json()

        # 3. Package lint
        r = client.post("/api/yt/package-lint", json={"title": "Why Python is Dying in 2026", "thumb_text": "THE END"})
        assert r.status_code == 200
        assert "score" in r.json()

        # 4. Formulas
        r = client.get("/api/yt/formulas")
        assert r.status_code == 200
        assert len(r.json()["formulas"]) == 21

