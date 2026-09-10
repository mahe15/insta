# CLIPER

**Your private Telegram clip studio, built in Python.** Send a long video, review a ranked shortlist, and receive captioned vertical clips.

**New: square clips with hook titles, category music, Instagram publishing and five-niche faceless carousels.** See [Feature 1 / Feature 2 setup and Telegram controls](FEATURES.md) for local account configuration, character images and scheduling.

```text
Telegram link / video upload
  → persistent SQLite queue
  → audio-only download + source validation (video links)
  → local faster-whisper transcription with word timestamps
  → full-transcript context → candidate discovery → editorial critique
  → duration validation + overlap / repeated-text removal
  → choose all, top 3, or custom clips
  → download only selected video ranges
  → square video on black vertical canvas + white hook title
  → FFmpeg captions + category music at 20% + NVENC H.264/AAC export
  → complete decode / resolution / duration / size / audio checks
  → Telegram delivery + downloadable subtitles and edit metadata
  → Instagram approval or automatic publishing (2-hour clip spacing)
```

## Start on this Windows computer

The project virtual environment and dependencies have already been installed in `.venv`.

1. Open `.env` in this project. Add your **`TELEGRAM_BOT_TOKEN`** from [@BotFather](https://t.me/BotFather). For no API key, choose **`AI_PROVIDER=chatgpt_browser`** and follow the ChatGPT browser setup below. Alternatively, choose an API provider and add its `OPENAI_API_KEY`, `XAI_API_KEY`, or `GEMINI_API_KEY` locally.
2. Start the bot:

   ```powershell
   .\scripts\start.ps1
   ```

3. Message your bot `/whoami`. Put that numeric ID in **`ALLOWED_USER_IDS`**, then stop with Ctrl+C and start again. Until you set the allowlist, only `/whoami` is available.
4. Send `/start`, then a supported video URL. Choose clips from the shortlist. Leave this terminal running while it processes jobs.

You can get your user ID from an existing trusted source and fill all three values before the first start. Keep secrets in `.env`; it is excluded from Git and Docker builds.

Check setup without contacting any service:

```powershell
.\.venv\Scripts\python.exe -m cliper doctor
```

Add `--online` to verify the bot token and whether the configured AI model is visible to your account. It does not generate clips or validate a paid inference call. Exit code `2` means setup is incomplete.

## Try it without credentials

```powershell
.\scripts\demo.ps1
```

This creates a **1080×1920 spoken clip** and `preview.png` in `data/demo/<run>/`. It uses a designed studio card, system-generated speech, real Whisper word timestamps and your configured video encoder. On this machine, transcription uses CUDA and export uses the RTX 4060 NVENC encoder. The first run may download the configured Whisper model. Selection uses basic offline ranking; the sample is not a benchmark of virality or paid AI selection.

Windows uses its installed English speech voice. On Linux, install `espeak-ng`, or supply a local 15–30 second speech recording with `python -m cliper demo --audio 'path/to/speech.wav'`. Use `--width 720` for a smaller export. The old colored bars and test tone are available only through `python -m cliper demo --diagnostic --width 360`; these are intentional diagnostic footage, not broken video.

To process a real local video with local transcription and basic ranking, set `AI_PROVIDER=heuristic` in `.env`, then:

```powershell
.\.venv\Scripts\python.exe -m cliper run 'C:\Videos\podcast.mp4' --clips 5 --min-seconds 30 --max-seconds 60
```

For stronger contextual selection, choose OpenAI, xAI Grok, or Google Gemini with the matching API key. All three use the full context, candidate discovery and editorial critique pipeline. There is no automatic provider fallback when a call fails.

## Switch AI providers

### ChatGPT website with no API key

The experimental `chatgpt_browser` provider uses Python Playwright and a dedicated Chromium profile to send prompts to `https://chatgpt.com/`, read completed replies, validate JSON and pass approved segment IDs to the normal renderer. It performs source summarization, candidate discovery and editorial review through the website. Transcription and NVENC encoding keep using your local GPU settings.

```powershell
.\scripts\setup-browser.ps1
.\scripts\chatgpt-login.ps1
# Sign in yourself, wait for the chat page, then close the Chromium window.
.\.venv\Scripts\python.exe -m cliper browser-check
```

Select `/provider chatgpt` in Telegram, or set `AI_PROVIDER=chatgpt_browser` in `.env` and restart the bot. Local processing also supports `python -m cliper run 'C:\Videos\podcast.mp4' --provider chatgpt`. Aliases: `chatgpt`, `browser`, `chatgpt_browser`. Existing jobs retain their original provider; submit a new video to use this selection.

There are **no API charges or API keys** for this provider. ChatGPT's Free plan and current account limits still apply ([official Free Tier FAQ](https://help.openai.com/en/articles/9275245-using-chatgpt-s-free-tier-faq)). This is a website adapter, so UI changes or account verification can interrupt it. It uses the model available in the website session; `website-session` in metadata is not a claim about a particular model. It never switches to a paid API automatically.

The browser opens visibly by default. Keep the desktop session available while it works. `CHATGPT_BROWSER_TIMEOUT=240` bounds each response; `CHATGPT_BROWSER_MAX_CHARS=60000` bounds each outgoing prompt. Long transcripts are summarized in sections. Set `CHATGPT_BROWSER_HEADLESS=true` only after verifying the saved session works. Login always opens visibly. The standard Docker image does not install browser support; use this local Windows setup.

Sessions are stored in `data/browsers/chatgpt-profile/`, excluded from Git. Prompts become website conversations under your account's ChatGPT data settings. Do not share the profile directory. CLIPER never imports your everyday browser cookies, enters your password, bypasses verification or works around account limits. When login expires or a limit is reached, complete any required website action yourself and use `/retry JOB`. If a completed reply is malformed, one schema repair is attempted; partial replies and mismatched request IDs are rejected. No raw browser replies or cookies are written to application logs.

For entirely offline operation without a website account, `/provider heuristic` remains available with basic ranking.

### API providers

Add the keys for the providers you want to use to the local `.env`:

```dotenv
AI_PROVIDER=xai

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini

XAI_API_KEY=
XAI_MODEL=grok-4.6

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

`AI_PROVIDER` accepts `openai`, `xai`, `gemini`, or `heuristic`; `grok` is an alias for `xai`. Only the chosen provider's key is required. An OpenAI key is **not** required for Grok or Gemini. Model names can be changed independently in the corresponding `*_MODEL` variable; select a model your account can access that supports structured output. Grok/Gemini requests currently use low reasoning effort and reserve an additional 4096 completion tokens for reasoning. Choose models supporting that effort setting. API costs depend on your provider and model.

Restart the bot after changing `.env`. Once your keys are configured, switch instantly from your private Telegram chat:

```text
/provider grok
/provider gemini
/provider openai
/provider heuristic
```

`/provider` shows the current choice, model and which providers have keys configured (never their values). `/provider default` removes your Telegram override and follows `AI_PROVIDER` again. The choice persists per owner across restarts. New jobs save the selected provider and model; changing preferences or environment defaults does not reroute jobs already submitted with a saved selection. Old jobs created before provider selection was added have no saved choice and use the environment default until reanalyzed; cached analysis keeps its recorded method.

To override the environment for one local run or setup check:

```powershell
.\.venv\Scripts\python.exe -m cliper run 'C:\Videos\podcast.mp4' --provider gemini
.\.venv\Scripts\python.exe -m cliper doctor --provider xai --online
```

OpenAI uses its Responses API. Grok and Gemini use their official OpenAI-compatible chat endpoints with JSON Schema and local Pydantic validation. The shared Python SDK sends Grok requests directly to `api.x.ai` and Gemini requests directly to `generativelanguage.googleapis.com`; using that SDK does not send their transcripts to OpenAI. [xAI structured output documentation](https://docs.x.ai/developers/model-capabilities/text/structured-outputs) and [Google's compatibility documentation](https://ai.google.dev/gemini-api/docs/openai) describe these interfaces.

## Install on another machine

Requires **Python 3.11–3.13**, disk space for source videos and speech models, and internet for the first model download. This workspace and `.env.example` use the RTX 4060 profile: Whisper `small`, CUDA `int8_float16`, and NVIDIA NVENC video encoding. For CPU-only machines, set `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, and `VIDEO_ENCODER=libx264` in `.env`.

Windows:

```powershell
.\scripts\setup.ps1
# On Windows with an NVIDIA GPU, install the CUDA libraries and save GPU settings:
.\scripts\setup-gpu.ps1
# If Python is not on PATH:
.\scripts\setup.ps1 -PythonPath 'C:\Path\To\python.exe'
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[transcribe,dev]'
cp .env.example .env
python -m cliper doctor
python -m cliper bot
```

FFmpeg is resolved from `FFMPEG_PATH`, then PATH, then the `imageio-ffmpeg` packaged executable. It must include the selected encoder (`h264_nvenc` or `libx264`), AAC, `libass`, `boxblur`, and `loudnorm`. This project probes videos using OpenCV and FFmpeg, so a separate ffprobe is not required for its render checks. A complete system FFmpeg installation remains useful for downloader compatibility.

YouTube extraction can require **Node.js or Deno**. Install a current supported runtime on PATH. Node is explicitly enabled when found. Platform changes, region/account restrictions, or anti-bot checks can still cause download failures; update `yt-dlp[default]` and review its error. The bot does not bypass access restrictions. Use an uploaded file or local video if necessary.

## RTX 4060 / 8 GB GPU settings

This computer is configured with:

```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=int8_float16
GPU_DEVICE_INDEX=0
VIDEO_ENCODER=h264_nvenc
```

Whisper runs on CUDA and final H.264 export uses the RTX's NVENC encoder. Quantized weights and float16 computation reduce transcription memory use. The worker processes one job at a time; the Whisper subprocess exits before rendering, releasing its model memory. The configured `small` model is a conservative choice for this 8 GB card. Available VRAM still depends on other programs running on the GPU.

The `gpu` installation extra supplies NVIDIA's CUDA 12 cuBLAS/runtime and cuDNN 9 wheels inside `.venv`. Windows DLL search paths are configured only for the running process; no driver replacement or system-wide PATH change is required. A sufficiently recent NVIDIA driver must already be installed. NVIDIA documents its [Windows cuDNN pip packages](https://docs.nvidia.com/deeplearning/cudnn/installation/latest/windows.html), and [faster-whisper documents its GPU library requirements](https://github.com/SYSTRAN/faster-whisper#gpu).

```powershell
# Already installed and configured in this workspace. For reinstalling:
.\scripts\setup-gpu.ps1
# Tests library loading, CUDA compute support, and an actual short NVENC encode:
.\.venv\Scripts\python.exe -m cliper doctor
```

The CUDA setting is explicit: a missing GPU/library fails with an error rather than silently moving transcription to the CPU. NVENC failures likewise remain visible. CPU decoding, subtitle composition, face detection and audio processing are still part of the pipeline; this is not an entirely GPU-resident editor. Grok/Gemini/OpenAI calls continue to run at their respective API providers.

Each new transcription writes `transcript.runtime.json` with the actual device and compute type, and clip JSON metadata records the encoder. Existing cached transcripts and validated exports may be reused on retry. Submit a new video job to exercise the new GPU configuration from the beginning.

## Telegram controls

| Command | Action |
|---|---|
| `/start`, `/help` | Open the studio and command help |
| `/whoami` | Show your numeric Telegram user ID |
| Send URL or `/clip URL` | Queue a supported source |
| Send video / video document | Process an upload up to the cloud download limit |
| `/jobs` | Last 10 jobs |
| `/status JOB` | Current stage; reopen a waiting shortlist |
| `/render JOB 1,3,5` | Generate specific clip numbers |
| `/render JOB all` | Generate the complete shortlist |
| `/cancel JOB` | Stop queued or running work |
| `/retry JOB` | Resume a failed job, preserving completed work |
| `/export JOB` | ZIP of transcript, SRT, ASS, edit plans and QA reports |
| `/settings` | View defaults and setting examples |
| `/provider` | Show available providers, selected model and key configuration status |
| `/provider grok` | Choose xAI Grok for new videos (`xai` also works) |
| `/provider gemini` | Choose Google Gemini for new videos |
| `/provider openai` | Choose OpenAI for new videos |
| `/provider heuristic` | Use basic offline selection |
| `/provider default` | Follow the environment's `AI_PROVIDER` again |
| `/clips 5` | Request 1–10 clips |
| `/length 30-60` | Length range, within 10–120 seconds |
| `/style studio` | `studio` mint highlight, `bold` yellow highlight, or `minimal` white captions |
| `/captions on` | Toggle burned-in captions; subtitle sidecars are still exported |
| `/reframe auto` | `auto`, `blur`, or `center` |
| `/language auto` | Whisper language detection, or language code such as `en` or `hi` |
| `/resolution 1080` | 1080×1920 or 720×1280 |
| `/auto on` | Automatically render all shortlisted clips for new jobs |
| `/cleanup` | Remove expired completed, failed or cancelled jobs |

Settings are saved per owner, and each job takes a snapshot when submitted. A shortlist may contain fewer clips than requested if the source lacks enough distinct, complete moments. Use a wider length range for difficult sources.

Only allowlisted users in **private chats** can submit jobs, change settings, or access results. Job actions check ownership again. Source links must use HTTPS and an allowlisted provider hostname. Default providers: YouTube, Vimeo and Twitch. Collection URLs are capped to the first item; send a specific video URL for predictable results. Arbitrary direct HTTP downloads are intentionally not exposed by the bot; use Telegram uploads or the local CLI for other files.

## What the editing pipeline does

- **Selection:** Reads the full bounded transcript to build context, discovers candidates in overlapping windows, then critiques candidates against surrounding source speech. It validates actual segment IDs, length, long gaps and scoring constraints before removing overlaps and near-duplicate text.
- **Scoring:** Hook 25%, payoff 25%, standalone clarity 25%, emotion 10%, usefulness 15%. Scores are editorial estimates, not probabilities, predicted views, or measured virality. The offline heuristic is clearly labelled and deliberately scores conservatively.
- **Captions:** Real Whisper word timestamps drive short stationary phrases with the spoken word highlighted. Text is escaped before writing ASS, and captions stay above common bottom controls. SRT and ASS remain available for later editing.
- **Reframing:** Samples faces once per second using OpenCV, chooses a smoothed face-centered crop only when detection is sufficiently consistent and single-face, and otherwise preserves the full frame on a blurred background. Scene-change samples are saved in the vision report. This is conservative face detection, **not active-speaker identification**, and the model does not inspect frames when ranking clips.
- **Audio/export:** Normalizes loudness, encodes H.264/AAC with a Telegram-aware bitrate budget, strips source metadata and enables streaming playback. Spoken content and timing stay intact; it does not remove fillers or splice words together.
- **QA:** Checks dimensions, duration, audio presence, effective silence, file size, and decodes the entire rendered clip. Failed technical validation triggers one lower-bitrate blurred-layout retry. This is **technical QA**, not a guarantee of factual correctness, accurate transcription, readable typography for every language, or perfect face visibility.

There is no web dashboard, subscription system, social publishing, automatic soundtrack, fabricated hook voiceover, or view-growth guarantee. Review clips before publishing. Install fonts covering the source language; the Docker image includes Noto fonts, while Windows uses available system fonts through libass.

## Reliability, limits and storage

`data/jobs.sqlite3` tracks jobs, preferences, selections and delivery checkpoints. Each job has its own `data/jobs/<id>/` directory containing the downloaded source, audio, transcript, analysis and exports. Originals supplied through the CLI remain at their original paths and are never deleted by retention.

One worker processes media at a time, while Telegram handlers remain responsive. A process lock prevents multiple CLIPER instances using the same data directory. Restarted analysis jobs reuse saved transcripts and analysis, and restarted render jobs reuse validated exports. Successful deliveries are checkpointed. Telegram does not offer an idempotency key for video sends: a crash or network timeout after acceptance but before recording success can cause a duplicate delivery.

Defaults in `.env.example`:

| Limit | Default |
|---|---:|
| Source duration | 120 minutes |
| Source download size | 1500 MB |
| Minimum free disk | 3000 MB |
| Active/awaiting jobs | 3 |
| Retention for finished jobs | 7 days |
| Telegram cloud upload download | 20 MB |
| Export file budget | below 49,000,000 bytes |

Retention runs on startup and hourly, and only affects terminal jobs older than the configured period. A cancelled or failed job keeps artifacts until retention or cleanup. Demo folders and cached Whisper models are not automatically deleted. Logs rotate at 2 MB with three backups. Known configured secrets are redacted from error messages; transcripts and exported metadata remain private local files.

OpenAI, Grok and Gemini modes send transcript text and selected surrounding passages to the chosen provider. OpenAI Responses requests use `store=False`; this flag is not sent to Grok/Gemini chat endpoints. Each provider's applicable data handling policies still apply. Local Whisper keeps source audio on the machine. Heuristic mode makes no LLM calls. Model files are downloaded on first transcription. The input character budget and source-duration limit bound analysis size; provider usage still depends on the chosen model and source length.

## Docker / always-on deployment

Fill `.env`, then on a Docker host:

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

The image runs as a non-root user and uses a named volume for jobs/models. No public port or webhook is required; it uses Telegram long polling. Do not run a second polling instance with the same bot token. CPU transcription and encoding can be slow for long sources; use shorter videos or a smaller Whisper model if needed. GPU mode requires a separately configured CUDA-compatible host/container and matching CTranslate2 libraries; the included Dockerfile is CPU-only.

The Docker configuration is included for deployment; it has not been built on this Windows environment. The supplied Compose file explicitly overrides the local GPU settings with CPU settings because the included image does not bundle the GPU runtime. For this RTX 4060 setup, run the bot directly on Windows with `scripts/start.ps1`. Telegram and paid AI integration require your credentials and must be live-tested after configuration.

## Development and verification

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover ownership, URL restrictions, bounded timestamp selection, deduplication, persisted settings, queue capacity, restart recovery, cancellation, delivery checkpoints, AI request staging with a fake provider, escaping, real FFmpeg exports and decoding. The suite does not require Telegram credentials, an AI key, or model downloads. GitHub Actions runs the suite on Linux.

See [VERIFICATION.md](VERIFICATION.md) for the checks actually run in this workspace and the remaining live checks. `requirements-windows.lock` records the tested Windows environment; standard cross-platform installation uses `pyproject.toml` or `requirements.txt`.

Key modules: `bot.py` handles Telegram; `storage.py` owns durable job state; `pipeline.py` coordinates work; `selection.py` handles editorial analysis; `transcribe.py` runs isolated Whisper; `vision.py` plans crops; `captions.py` writes timed subtitles; `media.py` downloads, renders and verifies; `cli.py` supplies local commands.

## Troubleshooting

- **Private bot response:** Set your numeric ID in `ALLOWED_USER_IDS`, restart, and use a private chat.
- **API key missing/model unavailable:** Set the matching `OPENAI_API_KEY`, `XAI_API_KEY` or `GEMINI_API_KEY` and an accessible structured-output model, then restart. Use `doctor --provider gemini --online` (or `xai`/`openai`). `/provider` shows your saved choice; `/provider default` follows the environment again. `heuristic` works without an AI key but has substantially simpler selection.
- **Model download failure:** First transcription needs access to Hugging Face. Model files live under `data/models`. Retry once connectivity is available.
- **Missing CUDA DLL or CUDA device:** Run `scripts/setup-gpu.ps1`, then `doctor`. A driver reporting CUDA 13 does not by itself install the CUDA 12/cuDNN libraries used by Whisper; the project GPU extra provides those libraries.
- **NVENC unavailable:** Check `doctor` and your NVIDIA driver. The selected FFmpeg build must include `h264_nvenc`. GPU encoding is not silently replaced by CPU encoding.
- **Queue full:** Waiting shortlists count toward the limit. Render or cancel them with `/status JOB` or `/cancel JOB`.
- **No suitable moments:** Try `/length 15-90`, clear speech, or a shorter source. The pipeline avoids padding the shortlist with invalid clips.
- **Missing language glyphs:** Install a font for that script and restart. Prefer `minimal` style if dense captions are hard to read.
- **Poor automatic crop:** Use `/reframe blur` and submit a new job. This preserves slides and multiple people.
- **Telegram delivery failed:** Fix connectivity, then `/retry JOB`. Already checkpointed clips are skipped.
- **Upload interrupted:** Send the attachment again; the original Telegram download may not have completed.
- **Another process uses the data directory:** Stop the other bot/CLI process first. Do not delete a live lock to start a competing worker.

## Primary implementation references

[Telegram Bot API](https://core.telegram.org/bots/api) documents file transfer methods and current cloud limits. [python-telegram-bot ApplicationBuilder](https://docs.python-telegram-bot.org/en/stable/telegram.ext.applicationbuilder.html) documents application lifecycle hooks. [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) documents typed Responses parsing. [faster-whisper](https://github.com/SYSTRAN/faster-whisper) documents local transcription and word timestamps. [yt-dlp](https://github.com/yt-dlp/yt-dlp) documents provider downloading and JavaScript runtimes. [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html) documents crop, subtitles, blur and audio filters.
