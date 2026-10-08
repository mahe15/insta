"""One real ChatGPT web-research check; never queues or publishes a post."""
import asyncio
import json
from pathlib import Path

from cliper.config import Config
from cliper.x_content import ResearchInput, commons_image, research


async def main():
    cfg = Config.load()
    directory = Path("data/verification/x-studio-live")
    directory.mkdir(parents=True, exist_ok=True)
    print("Starting current football research in the existing shared ChatGPT profile; no publishing.", flush=True)
    result = await research(cfg, ResearchInput(category="football", keywords="Official football club or league announcement", hours=24), [])
    (directory / "research.json").write_text(json.dumps(result, indent=2), "utf-8")
    print(json.dumps({"topic": result["research"]["topic"], "sources": len(result["research"]["sources"]), "flags": result["flags"], "text": result["text"]}), flush=True)
    try:
        media = await commons_image(result["research"]["media_query"], directory)
        (directory / "media.json").write_text(json.dumps(media, indent=2), "utf-8")
        print("Real public-domain media found: " + str(bool(media)), flush=True)
    except Exception as exc:
        print("Media lookup unavailable: " + type(exc).__name__, flush=True)


asyncio.run(main())
