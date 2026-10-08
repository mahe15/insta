"""Local end-to-end sample. Does not enqueue or publish anything."""
import asyncio
import json
import time

from cliper.config import Config
from cliper.models import Preferences
from cliper.pipeline import Pipeline, safe_error
from cliper.speed_profile import preset


async def main():
    cfg = Config.load()
    cfg.browser_timeout = 180
    folder = cfg.data_dir / "verification" / "speed-studio-live"
    folder.mkdir(parents=True, exist_ok=True)
    prefs = preset(cfg.snapshot_ai(Preferences()), clips=2, auto_publish=False, auto_render=False)
    pipeline = Pipeline(cfg)
    async def progress(message):
        print(message, flush=True)
    started = time.monotonic()
    try:
        async with asyncio.timeout(600):
            analysis = await pipeline.analyze("https://www.youtube.com/watch?v=Fiq9XMRr4jg", folder, prefs, progress)
            output = await pipeline.render_one(folder, analysis.clips[0], prefs)
            result = {"status": "rendered", "output": str(output), "analysis_method": analysis.method,
                      "clips": len(analysis.clips), "elapsed_seconds": round(time.monotonic()-started, 2),
                      "quality": json.loads(output.with_suffix(".json").read_text("utf-8"))["quality"]}
    except Exception as exc:
        result = {"status": "blocked", "error": safe_error(exc, cfg), "elapsed_seconds": round(time.monotonic()-started, 2)}
    (folder / "live-result.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
