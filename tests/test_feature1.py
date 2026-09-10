import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from cliper import remote_media
from cliper.captions import write_captions
from cliper.media import filter_graph, quality_check, render
from cliper.models import Analysis, Preferences
from cliper.pipeline import Pipeline
from cliper.process import run
from cliper.publishing import InstagramPublisher, PublishStore, caption_text
from cliper.storage import Store, write_json


def test_square_title_and_no_caption_switch(tmp_path, transcript, clip):
    prefs = Preferences(width=360, captions=False)
    graph, mode = filter_graph(prefs, {}, "a.ass")
    assert mode == "square_hook" and "crop=360:360" in graph and "color=black" in graph
    assert "ass=filename" in graph
    ass = write_captions(tmp_path, transcript, clip, prefs).read_text("utf-8-sig")
    assert clip.title in ass and "\\fnArial" in ass and "Dialogue: 0" not in ass


async def test_audio_first_and_selected_range_relative_timestamps(cfg, transcript, clip, monkeypatch):
    folder = cfg.data_dir / "job"
    folder.mkdir()
    audio = folder / "audio.webm"
    audio.touch()
    selected = clip.model_copy(update={"start": 5, "end": 19})
    audio_mock = AsyncMock(return_value=(audio, {"duration": 40, "audio": True}))
    monkeypatch.setattr(remote_media, "audio", audio_mock)
    monkeypatch.setattr("cliper.media.download", AsyncMock(side_effect=AssertionError("Full video downloaded")))
    monkeypatch.setattr("cliper.media.probe", AsyncMock(side_effect=AssertionError("Audio treated as video")))
    monkeypatch.setattr("cliper.media.transcribe", AsyncMock(return_value=transcript))
    monkeypatch.setattr("cliper.pipeline.select", AsyncMock(return_value=Analysis(
        title="test", language="en", duration=40, method="test", clips=[selected])))
    pipeline = Pipeline(cfg)
    await pipeline.analyze("https://youtu.be/test", folder, Preferences(), AsyncMock())
    audio_mock.assert_awaited_once()
    write_json(folder / "transcript.json", transcript.model_dump())
    range_mock = AsyncMock(return_value=folder / "range.mp4")
    monkeypatch.setattr(remote_media, "section", range_mock)

    async def fake_render(source, directory, shifted, local_clip, *args):
        assert local_clip.start == 0 and local_clip.end == 14
        assert shifted.segments[0].start == 0 and shifted.segments[0].words[0].start == 0
        directory.mkdir()
        output = directory / "clip_01.mp4"
        output.touch()
        write_json(output.with_suffix(".json"), {})
        return output

    monkeypatch.setattr("cliper.media.render", fake_render)
    output = await pipeline.render_one(folder, selected, Preferences())
    assert range_mock.await_args.args[2:4] == (5, 19)
    assert json.loads(output.with_suffix(".json").read_text())["clip"]["start"] == 5


async def test_real_square_render_with_twenty_percent_music(cfg, transcript, clip):
    from cliper.music import folders
    folders(cfg.music_dir)
    source = cfg.data_dir / "source.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=navy:s=640x360:r=30:d=3",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-c:a", "aac",
               "-shortest", str(source)])
    track = cfg.music_dir / "Chill - Ambient" / "track.wav"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=200:duration=1", str(track)])
    short = clip.model_copy(update={"end": 2.5})
    prefs = Preferences(width=360)
    output = await render(source, cfg.data_dir / "exports", transcript, short, prefs, cfg, lambda: False)
    assert (await quality_check(output, short, prefs, cfg, lambda: False))["full_decode"] == "passed"
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["music"]["gain"] == .2 and metadata["music"]["file"] == str(track.resolve())


def test_publish_approval_idempotence_spacing_and_ownership(cfg):
    pub = PublishStore(Store(cfg.data_dir))
    first = pub.add(42, 42, "job:1", "f1", "clips", ["a.mp4"], "caption", ["a"] * 10, auto=True)
    second = pub.add(42, 42, "job:2", "f1", "clips", ["b.mp4"], "caption", [], auto=True,
                     predecessor=first["id"], gap=7200)
    assert pub.add(42, 42, "job:1", "f1", "clips", ["a.mp4"], "caption", [])["id"] == first["id"]
    assert pub.claim()["id"] == first["id"] and pub.claim() is None
    pub.update(first["id"], state="published", published_at=time.time())
    assert pub.claim() is None
    pub.update(first["id"], published_at=time.time() - 7201)
    assert pub.claim()["id"] == second["id"]
    manual = pub.add(42, 42, "job:3", "f1", "clips", ["c.mp4"], "caption", [])
    assert pub.claim() is None
    with pytest.raises(ValueError):
        pub.decide(manual["id"], 99, True)
    pub.decide(manual["id"], 42, True)
    pub.hold_auto(42, "f1")
    assert pub.claim()["id"] == manual["id"]
    assert caption_text("caption #old", ["#a", "b", "c", "d", "e", "f"]).count("#") == 5


@pytest.mark.parametrize("uncertain", [False, True])
async def test_official_publish_flow_and_uncertain_outcome(cfg, monkeypatch, uncertain):
    pub = PublishStore(Store(cfg.data_dir))
    pub.store.save_prefs(42, Preferences(auto_publish=True))
    source = cfg.data_dir / "clip.mp4"
    source.write_bytes(b"fixture")
    monkeypatch.setattr("cliper.publishing.account_config", lambda *args: ({"ig_user_id": "123"}, "secret", "https://graph.instagram.com/v23.0"))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "https://media.example.com")
    monkeypatch.setenv("PUBLIC_MEDIA_DIR", str(cfg.data_dir / "public"))
    post = pub.add(42, 42, "fixture", "f1", "clips", [source], "caption", [], auto=True)
    requests = []

    def response(req):
        requests.append(req)
        assert req.headers["authorization"] == "Bearer secret"
        if req.url.path.endswith("media_publish"):
            if uncertain:
                raise httpx.ReadTimeout("uncertain", request=req)
            return httpx.Response(200, json={"id": "published-1"})
        if req.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        return httpx.Response(200, json={"id": "container-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        publisher = InstagramPublisher(pub, client)
        if uncertain:
            with pytest.raises(httpx.ReadTimeout):
                await publisher.process(pub.claim())
            assert pub.get(post["id"])["state"] == "uncertain"
            with pytest.raises(ValueError):
                pub.decide(post["id"], 42, True)
        else:
            assert await publisher.process(pub.claim()) == "published-1"
            assert pub.get(post["id"])["state"] == "published"
    assert len(requests) == 3


@pytest.mark.parametrize("status", ["EXPIRED", "PUBLISHED", "FINISHED"])
async def test_carousel_containers_retry_and_order(cfg, monkeypatch, status):
    from urllib.parse import parse_qs

    pub = PublishStore(Store(cfg.data_dir))
    paths = []
    for n in range(4):
        path = cfg.data_dir / f"slide{n}.jpg"
        path.write_bytes(b"fixture")
        paths.append(path)
    monkeypatch.setattr("cliper.publishing.account_config", lambda *args: (
        {"ig_user_id": "123"}, "secret", "https://graph.instagram.com/v23.0"))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "https://media.example.com")
    monkeypatch.setenv("PUBLIC_MEDIA_DIR", str(cfg.data_dir / "public"))
    post = pub.add(42, 42, "carousel", "f2", "dark", paths, "Caption", ["one"])
    pub.decide(post["id"], 42, True)
    children, published = [], []

    def response(req):
        body = parse_qs(req.content.decode()) if req.method == "POST" else {}
        if req.method == "GET":
            return httpx.Response(200, json={"status_code": status if req.url.path.endswith("parent") else "FINISHED"})
        if req.url.path.endswith("media_publish"):
            published.append(body)
            return httpx.Response(200, json={"id": "published"})
        if body.get("media_type") == ["CAROUSEL"]:
            assert body["children"] == ["child1,child2,child3,child4"]
            return httpx.Response(200, json={"id": "parent"})
        children.append(body)
        assert body["image_url"][0].endswith(f"/{len(children)}.jpg")
        assert body["is_carousel_item"] == ["true"]
        return httpx.Response(200, json={"id": f"child{len(children)}"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        publisher = InstagramPublisher(pub, client)
        if status == "FINISHED":
            await publisher.process(pub.claim())
            assert len(published) == 1 and pub.get(post["id"])["state"] == "published"
        else:
            with pytest.raises(ValueError):
                await publisher.process(pub.claim())
            result = pub.get(post["id"])
            assert not published
            if status == "EXPIRED":
                assert result["container"] is None and "children" not in json.loads(result["payload"])
            else:
                assert result["state"] == "uncertain"


def test_range_size_limit_is_not_the_full_source_size(cfg):
    assert "--max-filesize" not in remote_media.arguments("https://youtu.be/test", cfg, "range")
