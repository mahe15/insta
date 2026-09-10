import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest

from cliper.cache import export_identity
from cliper.carousel import compare_images, inspect_image
from cliper.carousel_models import Calculation, CarouselPlan, Slide
from cliper.creative import plan_audit, slide_prompt, text_matches
from cliper.editorial import attention_report, boundaries, choose_hook
from cliper.media import filter_graph, quality_check
from cliper.models import Analysis, Preferences
from cliper.pipeline import Worker
from cliper.process import run
from cliper.publishing import PublishStore, asset_hash, stage_assets
from cliper.storage import Store, write_json


def plan():
    return CarouselPlan(topic="Habit friction", pillar="Habits", hook="Make starting easier today", caption="Try one useful step.",
        hashtags=["habits"], slides=[Slide(text=text, environment="Library", action="Reading a book", lighting="Warm",
            camera="Medium shot", mood="Reflective", image_prompt="Original character reading a book in a calm library")
            for text in ["Make starting easier today", "Put the book where you sit", "Read one page before your phone", "Try it once tonight"]])


def test_grounded_hook_options_and_no_invented_number():
    source = "I tested one idea before building. That conversation changed my plan."
    title, _ = choose_hook("Earn 10000 by tomorrow", ["Test demand before building", "You won't believe this"], source)
    assert title == "Test demand before building"
    title, _ = choose_hook("Earn 10000 by tomorrow", [], source)
    assert "10000" not in title


def test_edge_trimming_preserves_speech_and_duration(transcript):
    segments = [s.model_copy(deep=True) for s in transcript.segments[:4]]
    segments[0].start = 0
    segments[0].words[0].start = .6
    start, end = boundaries(segments, 0, 20, Preferences(min_seconds=15, max_seconds=30))
    assert start == pytest.approx(.52) and end == pytest.approx(19.12)
    assert boundaries(segments, 0, 20, Preferences(min_seconds=20, max_seconds=30)) == (0, 20)
    assert boundaries(segments, 0, 20, Preferences(trim_edges=False)) == (0, 20)


def test_attention_low_confidence_and_pauses_are_explicit(transcript):
    for segment in transcript.segments:
        for word in segment.words:
            word.confidence = .1
    report = attention_report(transcript.segments, 0, 40, "Test demand before building")
    assert "low_transcription_confidence" in report["flags"]
    assert report["automatic_ready"] is False and report["pauses"]


def test_cache_changes_on_clip_source_and_music(cfg, transcript, clip):
    source = cfg.data_dir / "video.mp4"
    source.write_bytes(b"first")
    reference = {"path": str(source)}
    prefs = Preferences()
    initial = export_identity(reference, transcript, clip, prefs, cfg)
    assert export_identity(reference, transcript, clip.model_copy(update={"title": "Another hook"}), prefs, cfg) != initial
    source.write_bytes(b"new source")
    assert export_identity(reference, transcript, clip, prefs, cfg) != initial
    source.write_bytes(b"first")
    before = export_identity(reference, transcript, clip, prefs, cfg)
    folder = cfg.music_dir / "Chill - Ambient"
    folder.mkdir(parents=True)
    (folder / "track.wav").write_bytes(b"new track")
    assert export_identity(reference, transcript, clip, prefs, cfg) != before


def test_square_frame_tracks_subject_or_preserves_wide_group():
    graph, _ = filter_graph(Preferences(preserve_wide_groups=True), {"square_mode": "fit"}, "x.ass")
    assert "force_original_aspect_ratio=decrease" in graph
    graph, _ = filter_graph(Preferences(), {"square_mode": "track", "square_centers": [[0, .2], [3, .8]]}, "x.ass")
    assert "0.2000" in graph and "0.6000" in graph
    graph, _ = filter_graph(Preferences(smart_crop=False), {"square_mode": "fit"}, "x.ass")
    assert "force_original_aspect_ratio=increase" in graph
    graph, _ = filter_graph(Preferences(), {"square_mode": "fit"}, "x.ass")
    assert "force_original_aspect_ratio=increase" in graph


@pytest.mark.parametrize("expression", ["(-1)**0.5", "1000000**100", "(1000000**3)**100"])
def test_calculation_rejects_complex_or_unbounded_intermediates(expression):
    with pytest.raises(ValueError):
        Calculation(expression=expression, result=1, explanation="invalid")


def test_carousel_local_checks_before_spending_on_images():
    good = plan()
    assert plan_audit(good, [])["passed"]
    good.slides[1].text = good.slides[0].text
    assert "repeats" in " ".join(plan_audit(good, [])["errors"])
    good.slides[1].text = "word " * 41
    assert "40 words" in " ".join(plan_audit(good, [])["errors"])


def test_slide_prompt_has_exact_text_reference_and_series_context():
    value = plan()
    prompt = slide_prompt(value, value.slides[1], 2, {}, "dark", ["spelling error"])
    assert "CHARACTER REFERENCE" in prompt and "Slide 2/4" in prompt
    assert "150px bottom" in prompt and "spelling error" in prompt and value.slides[0].text in prompt
    assert "no swipe marker" in slide_prompt(value, value.slides[-1], 4, {}, "dark")


def test_flat_color_is_blank_and_recoded_reference_is_duplicate(tmp_path):
    flat = tmp_path / "flat.png"
    frame = np.full((400, 320, 3), (20, 80, 120), np.uint8)
    cv2.imwrite(str(flat), frame)
    with pytest.raises(ValueError, match="flat/blank"):
        inspect_image(flat)
    cv2.circle(frame, (160, 180), 90, (220, 220, 220), -1)
    cv2.imwrite(str(flat), frame)
    jpeg = tmp_path / "reencoded.jpg"
    cv2.imwrite(str(jpeg), frame)
    assert compare_images(flat, jpeg)["near_duplicate"]
    cv2.rectangle(frame, (0, 290), (300, 380), (10, 250, 60), -1)
    cv2.imwrite(str(jpeg), frame)
    assert not compare_images(flat, jpeg)["near_duplicate"]


def test_rejected_post_does_not_block_following_schedule(cfg):
    pub = PublishStore(Store(cfg.data_dir))
    first = pub.add(42, 42, "one", "f1", "clips", ["x.mp4"], "", [], auto=True)
    middle = pub.add(42, 42, "two", "f1", "clips", ["x.mp4"], "", [], auto=True, predecessor=first["id"], gap=7200)
    last = pub.add(42, 42, "three", "f1", "clips", ["x.mp4"], "", [], auto=True, predecessor=middle["id"], gap=7200)
    pub.update(first["id"], state="published", published_at=time.time() - 7300)
    pub.decide(middle["id"], 42, False)
    assert pub.claim()["id"] == last["id"]


def test_staged_assets_are_immutable_after_approval(cfg, monkeypatch):
    monkeypatch.setenv("PUBLIC_MEDIA_DIR", str(cfg.data_dir / "public"))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "https://media.example.com")
    path = cfg.data_dir / "x.mp4"
    path.write_bytes(b"approved")
    hashes = [asset_hash(path)]
    stage_assets([str(path)], "a" * 12, hashes)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed after review"):
        stage_assets([str(path)], "a" * 12, hashes)
    with pytest.raises(ValueError, match="differs"):
        stage_assets([str(path)], "a" * 12)


async def test_render_failure_cancels_owned_delivery(cfg, clip):
    store = Store(cfg.data_dir)
    job = store.create(42, 42, "source", Preferences(), state="rendering")
    other = clip.model_copy(update={"id": 2, "start": 20, "end": 39})
    write_json(store.directory(job["id"]) / "analysis.json", Analysis(title="", language="en", duration=40,
        method="test", clips=[clip, other]).model_dump())
    store.update(job["id"], selected=json.dumps([1, 2]))
    started, stopped = asyncio.Event(), asyncio.Event()
    async def deliver(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    worker = Worker(cfg, store, AsyncMock(), AsyncMock(), deliver)
    async def render(*args):
        if args[1].id == 2:
            await started.wait()
            raise ValueError("render failed")
        return Path("fixture.mp4")
    worker.pipeline.render_one = render
    with pytest.raises(ValueError, match="render failed"):
        await worker.process(store.get(job["id"]))
    assert stopped.is_set() and json.loads(store.get(job["id"])["delivered"]) == []


async def test_full_decode_not_just_first_seconds_and_black_content(cfg, clip, monkeypatch):
    path = cfg.data_dir / "black.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=360x640:d=2:r=30",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)])
    calls = []
    async def record(args, **kwargs):
        calls.append(args)
        return await run(args, **kwargs)
    monkeypatch.setattr("cliper.media.run", record)
    with pytest.raises(ValueError, match="effectively black"):
        await quality_check(path, clip.model_copy(update={"end": 2}), Preferences(width=360), cfg, lambda: False)
    decode = next(args for args in calls if "-xerror" in args)
    assert "-t" not in decode


@pytest.mark.parametrize(("observed", "expected", "matches"), [
    ("SAVE $1,000", "Save $1000.", True), ("Save 1000", "Save $1000", False),
    ("Do invest everything", "Do not invest everything", False),
    ("Growth of 10%", "Growth of 10", False), ("1.5 hours", "15 hours", False)])
def test_visual_text_comparison_preserves_meaning(observed, expected, matches):
    assert text_matches(observed, expected) is matches


async def test_audio_only_and_no_old_range_relabel(cfg, monkeypatch):
    from cliper import remote_media
    folder = cfg.data_dir / "audio"
    folder.mkdir()
    (folder / "audio-source.webm").write_bytes(b"fixture")
    write_json(folder / "audio-source.info.json", {"duration": 30})
    execute = AsyncMock()
    monkeypatch.setattr(remote_media, "execute", execute)
    await remote_media.audio("https://youtu.be/test", folder, cfg, lambda: False)
    args = execute.await_args.args[0]
    assert args[args.index("--format") + 1] == "bestaudio"
    ranges = cfg.data_dir / "range"
    ranges.mkdir()
    (ranges / "range.mp4").write_bytes(b"old content")
    write_json(ranges / "range.json", {"url": "https://youtu.be/old", "start": 0, "end": 5})
    with pytest.raises(ValueError, match="not downloaded"):
        await remote_media.section("https://youtu.be/new", ranges, 10, 15, cfg, lambda: False)
    assert not (ranges / "range.mp4").exists()
