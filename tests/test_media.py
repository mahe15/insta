import asyncio
import sys
import time

import pytest

from cliper.captions import ass_time, safe_ass, write_captions
from cliper.media import filter_graph, quality_check, render, validate_url
from cliper.models import Preferences
from cliper.process import JobCancelled, run


@pytest.mark.parametrize("url", ["http://youtube.com/watch?v=x", "https://127.0.0.1/a",
                                    "https://youtube.com.evil.test/x", "file:///tmp/x",
                                    "https://user:password@youtube.com/x", "https://youtube.com:8080/x",
                                    "https://localhost/a", "https://youtube.com/x\n--exec"])
def test_url_restrictions(cfg, url):
    with pytest.raises(ValueError):
        validate_url(url, cfg)


def test_video_host_and_subdomain(cfg):
    assert validate_url("https://www.youtube.com/watch?v=abc", cfg)
    assert validate_url("https://youtu.be/abc", cfg)


def test_captions_use_relative_timestamps_and_escape(tmp_path, transcript, clip):
    clip = clip.model_copy(update={"start": 5, "end": 19})
    ass = write_captions(tmp_path, transcript, clip, Preferences(width=360))
    content = ass.read_text(encoding="utf-8-sig")
    assert "0:00:00.00" in content
    assert "Why did" not in content
    assert "\\1c" in content
    assert "000000" not in safe_ass(r"{\p1}abc")
    assert "{" not in safe_ass(r"{\p1}abc")
    assert ass_time(59.999) == "0:01:00.00"


def test_reframe_fallback_and_no_caption_switch():
    graph, mode = filter_graph(Preferences(captions=False), {}, "internal.ass")
    assert mode == "blur" and "ass=filename" not in graph
    graph, mode = filter_graph(Preferences(), {"safe_crop": True, "centers": [[0, .2], [3, .8]]}, "a.ass")
    assert mode == "auto" and "if(lt(t" in graph


async def test_owned_process_cancellation():
    started = time.monotonic()
    stopped = False

    async def cancel():
        nonlocal stopped
        await asyncio.sleep(.3)
        stopped = True

    task = asyncio.create_task(cancel())
    with pytest.raises(JobCancelled):
        await run([sys.executable, "-c", "import time; time.sleep(20)"], cancelled=lambda: stopped)
    await task
    assert time.monotonic() - started < 5


async def test_process_timeout_and_nonzero():
    with pytest.raises(TimeoutError):
        await run([sys.executable, "-c", "import time; time.sleep(20)"], timeout=1)
    with pytest.raises(RuntimeError, match="exit 3"):
        await run([sys.executable, "-c", "raise SystemExit(3)"])


async def test_real_ffmpeg_render_and_quality_check(tmp_path, cfg, transcript, clip, monkeypatch):
    source = tmp_path / "source with spaces.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i",
               "testsrc2=size=320x180:rate=30:duration=3", "-f", "lavfi", "-i",
               "sine=frequency=440:duration=3", "-c:v", "libx264", "-preset", "ultrafast",
               "-c:a", "aac", "-shortest", str(source)])
    short = clip.model_copy(update={"end": 2.5})
    prefs = Preferences(width=360, reframe="blur")
    output = await render(source, tmp_path / "exports", transcript, short, prefs, cfg, lambda: False)
    qa = await quality_check(output, short, prefs, cfg, lambda: False)
    assert qa["width"] == 360 and qa["height"] == 640
    assert qa["audio"] and qa["full_decode"] == "passed"
    assert output.with_suffix(".json").exists()
    # Exercise the crop branch as well as blur using the actual FFmpeg build.
    output = await render(source, tmp_path / "center", transcript, short,
                          prefs.model_copy(update={"reframe": "center", "style": "minimal"}), cfg, lambda: False)
    assert output.stat().st_size > 1000
    # Verify FFmpeg evaluates the real moving-crop expression, using a deterministic vision fixture.
    from cliper.storage import write_json

    async def vision_fixture(args, **kwargs):
        if "cliper.vision" in args:
            from pathlib import Path
            write_json(Path(args[-1]), {"safe_crop": True, "centers": [[0, .25], [1, .7], [2, .5]]})
            return ""
        return await run(args, **kwargs)

    monkeypatch.setattr("cliper.media.run", vision_fixture)
    output = await render(source, tmp_path / "tracking", transcript, short,
                          prefs.model_copy(update={"reframe": "auto", "style": "bold"}), cfg, lambda: False)
    assert output.stat().st_size > 1000
