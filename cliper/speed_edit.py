"""Sparse, source-timed emphasis. Never rearranges events or changes playback speed."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .process import run

ASSETS = Path(__file__).resolve().parent / "assets" / "sfx"


def envelope_peaks(samples, rate):
    size = max(1, rate // 10)
    if len(samples) < size:
        return []
    blocks = samples[:len(samples) // size * size].reshape(-1, size)
    energy = np.sqrt(np.mean(blocks.astype(np.float64) ** 2, axis=1))
    baseline = max(.015, float(np.median(energy)))
    peaks = []
    for i in np.argsort(energy)[::-1]:
        t = float(i) / 10
        if energy[i] < max(.06, baseline * 1.65):
            break
        if t >= .5 and all(abs(t - p["time"]) >= 4 for p in peaks):
            peaks.append({"time": round(t, 2), "strength": round(float(energy[i] / baseline), 2)})
        if len(peaks) == 5:
            break
    return peaks


def make_plan(peaks, clip, prefs):
    duration = clip.end - clip.start
    # Never turn a sincere encounter into a comic sound gag.
    if clip.moment_type == "wholesome" or clip.music_category == "emotional_sad":
        return {"effects": [], "zoom": [], "reason": "Preserve the original emotional moment"}
    payoff = clip.payoff_time - clip.start if clip.payoff_time is not None else None
    eligible = [p for p in peaks if .5 <= p["time"] <= duration - .6]
    if payoff is not None:
        eligible = [p for p in eligible if abs(p["time"] - payoff) <= 1.5]
    # Only one accent at the strongest observed beat. Silence is better than random effects.
    chosen = eligible[:1]
    sound = "reaction.wav" if clip.moment_type == "reaction" else "reveal.wav"
    effects = [{"time": p["time"], "file": sound, "gain": prefs.sfx_gain} for p in chosen] if prefs.sound_effects else []
    zoom = [{"start": p["time"], "end": min(duration, p["time"] + .65)} for p in chosen] if prefs.reaction_zoom and clip.moment_type == "reaction" else []
    return {"effects": effects, "zoom": zoom, "audio_peaks": peaks,
            "reason": "Observed audio emphasis; editorial payoff when supplied. Not a visual event detector."}


async def plan(source, directory, clip, prefs, cfg, cancelled):
    if prefs.editorial_profile != "ishowspeed" or not (prefs.sound_effects or prefs.reaction_zoom):
        return {"effects": [], "zoom": []}
    if clip.moment_type == "wholesome" or clip.music_category == "emotional_sad":
        return make_plan([], clip, prefs)
    path = directory / f"clip_{clip.id:02}.energy.wav"
    await run([cfg.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-ss", str(clip.start), "-i", str(source), "-t", str(clip.end - clip.start),
               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(path)], cancelled=cancelled, timeout=120)
    with wave.open(str(path), "rb") as audio:
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        peaks = envelope_peaks(samples, audio.getframerate())
    result = make_plan(peaks, clip, prefs)
    for effect in result["effects"]:
        if not (ASSETS / effect["file"]).is_file():
            raise ValueError("The bundled CC0 sound pack is missing. Reinstall CLIPER before rendering Speed effects.")
    return result


def audio_graph(track, plan, length, prefs):
    """Voice sidechain ducks both BGM and SFX. The final limiter prevents summed clipping."""
    effects = plan["effects"]
    extras = (["-stream_loop", "-1", "-i", str(track)] if track else [])
    graph = ";[0:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,asplit=2[voice][side];"
    labels = []
    if track:
        norm = "loudnorm=I=-20:TP=-2:LRA=9,aresample=48000," if prefs.music_normalize else "aresample=48000,"
        graph += (f"[1:a]{norm}volume={prefs.music_gain:.3f},afade=t=in:d=0.25,"
                  f"afade=t=out:st={max(0,length-.6):.3f}:d=0.6[bed];")
        labels.append("[bed]")
    for i, effect in enumerate(effects):
        extras += ["-i", str(ASSETS / effect["file"])]
        index = i + (2 if track else 1)
        delay = round(effect["time"] * 1000)
        graph += (f"[{index}:a]aresample=48000,atrim=duration=1,asetpts=PTS-STARTPTS,"
                  f"volume={effect['gain']:.3f},afade=t=out:st=0.7:d=0.3,adelay={delay}:all=1,"
                  f"apad,atrim=duration={length:.3f}[fx{i}];")
        labels.append(f"[fx{i}]")
    graph += "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[bedmix];"
    if prefs.music_ducking or effects:
        graph += "[bedmix][side]sidechaincompress=threshold=.025:ratio=6:attack=8:release=180:makeup=1[ducked];[voice][ducked]"
    else:
        graph += "[side]anullsink;[voice][bedmix]"
    graph += "amix=inputs=2:duration=first:normalize=0,alimiter=limit=.95:level=false[aout]"
    return graph, extras
