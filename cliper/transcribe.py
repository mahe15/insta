"""Isolated transcription process; a cancelled job can release model RAM immediately."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .hardware import check_cuda
from .models import Segment, Transcript, Word
from .storage import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute", default="int8")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--language", default="auto")
    parser.add_argument("--cache", required=True)
    parser.add_argument("--beam-size", type=int, default=5)
    args = parser.parse_args()
    if not args.manifest and (not args.audio or not args.output):
        parser.error("Supply audio and output, or --manifest")
    if args.device == "cuda":
        check_cuda(args.device_index, args.compute)
    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute,
                         device_index=args.device_index, download_root=args.cache, cpu_threads=4)
    print(f"Whisper: device={model.model.device}, compute={model.model.compute_type}", flush=True)
    jobs = json.loads(args.manifest.read_text("utf-8")) if args.manifest else [{"audio": args.audio, "output": str(args.output)}]
    for job in jobs:
        transcribe_file(model, job["audio"], Path(job["output"]), args)


def transcribe_file(model, audio, output, args):
    segments, info = model.transcribe(
        audio, beam_size=args.beam_size, word_timestamps=True, vad_filter=True,
        language=None if args.language == "auto" else args.language,
        condition_on_previous_text=False, vad_parameters={"min_silence_duration_ms": 500})
    result = []
    # Re-segment using actual word timing so the selector can cut at sentence boundaries.
    pending = []

    def flush():
        if pending:
            result.append(Segment(start=pending[0].start, end=pending[-1].end,
                                  text=" ".join(w.text for w in pending), words=list(pending)))
            pending.clear()

    for segment in segments:
        if segment.no_speech_prob > .85 and segment.avg_logprob < -1:
            continue
        for w in segment.words or []:
            if not w.word.strip() or w.end <= w.start:
                continue
            if pending and (w.start - pending[-1].end > 1.2 or w.start - pending[0].start > 18):
                flush()
            pending.append(Word(start=max(0, w.start), end=w.end, text=w.word.strip(),
                                confidence=max(0, min(1, float(w.probability)))))
            if w.word.rstrip().endswith((".", "!", "?", "。", "！", "？")):
                flush()
        print(f"Transcribed {segment.end:.0f}s", flush=True)
    flush()
    transcript = Transcript(language=info.language, duration=info.duration, segments=result)
    write_json(output, transcript.model_dump())
    write_json(output.with_suffix(".runtime.json"), {"device": model.model.device,
                                                        "compute_type": model.model.compute_type,
                                                        "device_index": args.device_index,
                                                        "beam_size": args.beam_size,
                                                        "model": args.model})


if __name__ == "__main__":
    main()
