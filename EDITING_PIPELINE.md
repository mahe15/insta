# Editing pipeline upgrade

New clip defaults are 1080×1920, 60 fps, Natural colour and High-quality master. Settings and each project's editing dialog expose frame rate, colour finish and export quality. Existing completed videos are unchanged; rerender to apply the new pipeline. The render-cache version was changed so an old export cannot silently satisfy a new render request.

## Framing and typography

The renderer and ASS captions now share a layout calculation. For square crops, the hook sits just above the square video. For a preserved wide frame inside the square container, its anchor follows the actual fitted picture's upper edge. The gap is proportional to output width (27 pixels at 1080p). White hook text is measured using the installed bold Arial/DejaVu font, wrapped to fit, and scaled when needed. Caption baselines also follow the visible picture's lower edge with an inset and a vertical social-interface safe margin.

The Preserve frame option now also works in square-hook layouts. Background stays black. Lanczos scaling improves resizing; source detail still limits what an enlarged video can contain. Reaction emphasis scales the footage before framing and subtitle compositing, with a smooth, restrained pulse. Titles and subtitles remain stationary. Reducing the bitrate after a compact-size failure no longer changes the crop.

## Captions and language

Word times are clipped to the excerpt, sorted and normalized to ASS's centisecond precision. Equal-start words are retained as a phrase, overlaps are bounded by the next word, and zero-length cues are omitted. Highlighting ends with the spoken word; the phrase stays neutral through short pauses. Plain SRT and burned-in ASS use the same normalized groups.

Pixel-based line fitting replaces character-count-only typography. Romanization retains source timing. English translation uses short source-timed phrases rather than inventing English word alignment or squeezing an entire long segment into one caption. Multiword translation tokens render as phrases. This fixes layout/timing problems; transcription and translation accuracy still depend on the source transcript and model.

Hook guidance now favors one specific 4–8 word idea, a short readable headline and a payoff supported by the clip. It avoids repeating the opening speech word for word. No rendering setting can guarantee virality.

## Colour, motion and encoding

Natural adds mild contrast, saturation and sharpening; Vivid adds slightly more; Off skips the creative grade. Processing happens before black padding and typography. Tagged PQ/HLG input is converted through linear-light tone mapping into SDR BT.709 before grading. This needs FFmpeg's zscale and tonemap filters, available in the project's installed build. This is a restrained preset finish, not automatic shot-by-shot exposure or white-balance correction.

60 fps output preserves native high-frame-rate material; lower-rate footage uses frame duplication. It does not reconstruct new motion or recover missing resolution. FFmpeg documents this behavior for its [fps filter](https://ffmpeg.org/ffmpeg-filters.html#fps-1), and linear-light requirements for [tone mapping](https://ffmpeg.org/ffmpeg-filters.html#tonemap).

NVIDIA exports use the configured GPU with H.264 NVENC, P6/HQ, VBR/CQ19, lookahead, spatial adaptive quantization and B-frames. Full HD masters target up to 16 Mbps at 60 fps or 10 Mbps at 30 fps; content complexity and the encoder determine actual size. Encoding follows the quality controls described in [NVIDIA's FFmpeg guidance](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/ffmpeg-with-nvidia-gpu/index.html). FFmpeg scaling, libass typography and some filters still execute on CPU; encoding uses NVENC. AAC is 48 kHz/192 kbps for masters, and the mixed-audio limiter compensates its lookahead latency.

High-quality masters no longer inherit Telegram's cloud upload budget. If necessary, Telegram delivery creates a separate smaller file under the export's `delivery` folder. Studio downloads and publication assets retain the master. Compact mode remains available when a single small export is preferred.

## Verification

`scripts/verify_editing.py` renders existing local, caption-verified footage without publishing. The October 8 verification produced two 1080×1920, 60 fps, 10-second H.264 NVENC samples: a square crop and preserved wide frame. Both passed full decoding, audio-level, duration and resolution checks; sampled frames showed no black/frozen-content warnings. The hook and captions were inspected visually.

Artifacts are in `data/verification/editing-1080p60`. A 61.4 MB, 40-second master also produced a separate 31.9 MB Telegram copy at 60 fps with matching duration and an unchanged master. A tagged synthetic PQ input successfully decoded through the HDR conversion filter. These checks verify the pipeline, not every possible source file or subjective colour choice.

The full regression run passed 268 tests; two existing carousel prompt assertions still expect the previous single-scene layout. The subsequent final media/layout/web run passed all 38 tests. The production frontend builds successfully and the changed rendering modules pass Ruff. X publishing remains disabled.
