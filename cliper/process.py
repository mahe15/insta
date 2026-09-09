"""Bounded, shell-free processes with cancellation of the owned process tree."""
from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Callable
from pathlib import Path


class JobCancelled(Exception):
    pass


async def run(args: list[str], *, cwd: Path | None = None, timeout: int = 3600,
              cancelled: Callable[[], bool] = lambda: False) -> str:
    if cancelled():
        raise JobCancelled()
    kwargs = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})
    proc = await asyncio.create_subprocess_exec(
        *map(str, args), cwd=cwd, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT, **kwargs)
    # Keep only a bounded log tail. Download/transcription logs can otherwise fill RAM.
    chunks = bytearray()

    async def drain():
        while chunk := await proc.stdout.read(8192):
            chunks.extend(chunk)
            if len(chunks) > 256_000:
                del chunks[:-128_000]
        await proc.wait()

    reader = asyncio.create_task(drain())
    try:
        async with asyncio.timeout(timeout):
            while not reader.done():
                if cancelled():
                    raise JobCancelled()
                await asyncio.wait({reader}, timeout=.4)
            await reader
        output = chunks.decode("utf-8", errors="replace")
        if proc.returncode:
            raise RuntimeError(f"{Path(str(args[0])).name} failed (exit {proc.returncode}): {output[-2200:]}")
        return output
    finally:
        if proc.returncode is None:
            if os.name == "nt":
                killer = await asyncio.create_subprocess_exec(
                    "taskkill", "/PID", str(proc.pid), "/T", "/F",
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    await asyncio.wait_for(killer.wait(), timeout=3)
                except TimeoutError:
                    killer.kill()
                    await killer.wait()
                # Some restricted Windows sessions deny taskkill's process enumeration.
                # Our own child handle still permits direct termination.
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
            else:
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await proc.wait()
        if not reader.done():
            reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)
