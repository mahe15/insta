"""Optional local web worker; shares the existing exclusive engine lock."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from filelock import FileLock, Timeout

from .controls import Controls
from .faceless import FacelessWorker
from .pipeline import Worker
from .publishing import InstagramPublisher
from .x_studio import XWorker
from .youtube_publishing import YouTubePublisher


class WebRuntime:
    def __init__(self, cfg, store):
        self.cfg, self.store = cfg, store
        self.lock = FileLock(str(cfg.data_dir / "worker.lock"), timeout=0)
        self.tasks = []
        self.worker = None
        self.mode = "stopped"

    async def start(self):
        if self.mode == "local":
            return
        try:
            self.lock.acquire()
        except Timeout:
            self.mode = "attached"
            return
        controller = SimpleNamespace(cfg=self.cfg, store=self.store, app=None)
        controls = Controls(controller)
        controls.publications.web_only = True

        async def quiet(*args):
            return

        async def deliver(job, clip, output):
            controls.clip_publication(job, clip, output)

        self.worker = Worker(self.cfg, self.store, quiet, quiet, deliver, web_only=True)
        self.tasks = [asyncio.create_task(self.worker.run()),
                      asyncio.create_task(FacelessWorker(controls, web_only=True).run()),
                      asyncio.create_task(InstagramPublisher(controls.publications).run(quiet)),
                      asyncio.create_task(YouTubePublisher(controls.publications, cfg=self.cfg).run(quiet)),
                      asyncio.create_task(XWorker(self.cfg, self.store).run())]
        self.mode = "local"

    async def stop(self):
        if self.worker:
            await self.worker.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []
        self.worker = None
        if self.lock.is_locked:
            self.lock.release()
        self.mode = "stopped"

    def status(self):
        failed = any(t.done() and not t.cancelled() for t in self.tasks)
        return {"mode": self.mode, "healthy": not failed,
                "scope": "web jobs" if self.mode == "local" else "existing worker" if self.mode == "attached" else "paused"}
