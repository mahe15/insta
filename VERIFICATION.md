# Local verification — 8 September 2026

## Speed Studio and Latin-script text — October 2, 2026

- Full regression suite: **232 passed in 59.80 seconds**. Three subsequent Gemini repair/focus regression cases were added; all **38 Gemini tests passed in 5.72 seconds**. Repository Ruff and `pip check` passed. The full suite reports one existing Starlette test-client deprecation warning.
- Production React/TypeScript build passed (444.74 kB main JavaScript, 138.27 kB gzip). Read-only Chromium checks visited Studio, Speed Studio, Carousels, Publishing, Music and Settings at **1440×1100** and **390×844**, plus a real project. No horizontal overflow or page JavaScript errors occurred. Keyboard dialogs, search and mobile navigation passed. Speed Studio desktop and mobile screenshots were visually inspected.
- Isolated browser/API tests create a Speed job, persist its English/6–60 second preset without changing global preferences, and exercise language settings. Tests also cover local romanization, preservation of source word timing, cached phrase translation, licensed asset hashes, restrained sound planning, actual FFmpeg sound/zoom rendering, a Hindi-to-Latin subtitle render and a 120-point face-track expression decode.
- A **real Gemini website request through the original shared Chromium profile** analyzed IShowSpeed's official Ronaldo meeting video. The selected **18–64 second interval** was downloaded and corrected locally, then exported with **NVENC at 1080×1920, 46.0 seconds, 38,209,378 bytes**. Full decode/audio checks passed; peak audio was **−1.3 dB** and all **92 sampled content frames** passed black/static checks. Cover and source contact sheet were inspected. The wholesome classification correctly suppressed comic effects and reaction zoom.
- The last cached-selection render attempt took **22.78 seconds**; earlier AI discovery, repair and download work are excluded. It is not an end-to-end benchmark. Caption confidence and pause flags still require editorial review; no measured virality or perfect transcription is claimed. The real sample was not queued or published.
- The refreshed web server is available on port **8788** with the engine paused. Inspection found two existing queued publications, so verification did not start the publisher or change those entries. **Settings → System → Start engine** resumes normal processing, including that existing publishing queue.

Usage and research: [SPEED_STUDIO.md](SPEED_STUDIO.md). Real sample and results: `data/verification/speed-studio-live`. Browser screenshots/results: `data/verification/web-studio`.

## Web Studio — September 27, 2026

- **218 tests passed in 66.68 seconds**, including the new API and real Chromium workflow tests. After the final empty-error display fix, all **18 web API/browser tests passed again in 8.71 seconds**. Repository Ruff and `pip check` passed. Starlette emits one test-client deprecation warning; it does not fail the tests.
- React/TypeScript production build passed; the main JavaScript bundle is 436.75 kB (135.99 kB gzip). Prettier checks passed. The frontend lockfile is included with the source; generated dependencies and build output are ignored.
- Isolated tests exercise authentication, CSRF, origin/host restrictions, ownership, media range responses, managed uploads, real image decoding, credential write-only behavior, clip edits, selection/render queueing, settings persistence, cancellation, publication approval/scheduling and web-only worker claims/recovery. Browser mutation tests use a temporary database and no running publisher.
- Read-only Chromium checks loaded Studio, Carousels, Publishing, Music and Settings at **1440×1100** and **390×844**, plus project review. No horizontal page overflow or page JavaScript exceptions were detected. Dialog Escape handling, command search and mobile navigation passed. Desktop project/library and mobile carousel screenshots were visually reviewed.
- Screenshots and machine-readable results: `data/verification/web-studio`. The local server was refreshed with the final backend fixes; its final health check reported a local worker under the shared engine lock. Verification did not submit real generation jobs, send Telegram messages or publish to Instagram. Existing workspace jobs/publications remain real data, not test fixtures.

Operating guide: [WEB_STUDIO.md](WEB_STUDIO.md). Design and research: [WEB_DESIGN.md](WEB_DESIGN.md).

## Long-stream and editing upgrade — September 27, 2026

- **198 tests passed in 59.95 seconds.** Repository-wide `ruff check .` passed after correcting launcher/import lint issues. `pip check` reported no broken requirements. The offline doctor passed CUDA library/compute checks, a real NVENC encode and configured application prerequisites; it does not test live service authentication.
- Tests cover 8-hour and 20-hour planning at multiple budgets, timeline diversity, focus bounds, public-host allowlists/spoof rejection, caption rolling-text deduplication, absolute timestamp alignment, download concurrency/cancellation, one model load per transcription batch, retry reuse, frozen scan ranges when replay metadata changes, empty editorial batches, selected-audio duration checks, crop smoothing and installed Kick/Twitch VOD URL extractors. These are fixtures and local extractor checks, not live long-VOD downloads.
- A **live YouTube audio interval** from 1112.36 to 1124.36 seconds produced a **12.032-second, 385,102-byte mono WAV**, acquired in **13.22 seconds**. Its discovery transcription took **14.45 seconds**, including subprocess/model startup, using actual **CUDA / int8_float16 / small / beam 1**. This is a single sample, not a general throughput benchmark.
- The matching video interval was downloaded and rendered into `data/verification/stream-upgrade/render/clip_01.mp4`. The result is **1080×1920**, **11.967 seconds**, **9,194,912 bytes**. Rendering plus QA took **9.62 seconds**. Full decode and audio-level checks passed; all 24 sampled content frames passed the black/static checks. Peak audio was **−1.4 dB**. The saved cover image was visually inspected: square video, black vertical canvas, white hook above, and readable timed captions.
- That render used **YuNet 2023**, RTX NVENC, category music normalized before 20% gain, fades and speech ducking. YuNet's **232,589-byte** official artifact was rechecked after tests against SHA-256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`. Standard OpenCV detection runs on CPU; this is not a claim of CUDA face detection. The sample's hook was manually selected for technical validation, not generated by a newly live-tested AI response.
- Current local configuration allows the 12 platform groups and a 24-hour source maximum. The default long-source discovery budget is 24 minutes: **5% of 8 hours / 2% of 20 hours**. This coverage reduction can miss highlights and is not a measured end-to-end speedup. Captions-first cases avoid discovery audio entirely; selected ranges still receive correction work.
- The project's original shared Chromium profile was retained. No new live browser AI generation, Instagram publication, Telegram delivery or 8–20 hour Kick/Twitch end-to-end run was performed for this upgrade. Service availability, source accessibility and browser/account limits still apply.

Research and operating details: [LONG_STREAM_ARCHITECTURE.md](LONG_STREAM_ARCHITECTURE.md). Local measured results: `data/verification/stream-upgrade/results.json`. Earlier entries below describe earlier snapshots.

## Studio upgrade and Gemini clipping — September 10–11, 2026

The latest changes add editorial checks, stronger carousel planning/QA and a link-first Gemini website clipping route. The final browser configuration retains the original shared project Chromium profile for ChatGPT, Feature 2 Gemini images and Gemini clipping. No Chrome remote-debugging setup is required or retained.

- Final retained code: **152 tests passed in 54.79 seconds**, with Ruff and dependency checks passing. It includes actual local Chromium fixtures, actual FFmpeg media tests, simulated external AI/Instagram calls and a regression proving that all three website adapters share the original project profile and lock.
- The actual RTX 4060 NVENC sample is `data/verification/studio-upgrade/clip_01.mp4`: **1080×1920**, **57.967 seconds**, **39,498,864 bytes**. Full decode and audio checks passed. The 116 sampled video-content frames contained no flagged black/static intervals. The filled-square layout, white title and captions were visually inspected using the saved cover JPEG. Category music at 20% gain, fades and speech ducking were enabled. This uses a cached user source/transcript and a manually curated title; it does not measure virality or new AI selection.
- New automated cases cover hook grounding, valid edge trimming, caption confidence, cache invalidation, image/reference duplication, literal image-text checking, invalid arithmetic, upload cancellation, audio-only extraction, reviewed-asset hashes and publishing predecessor recovery.
- Gemini clipping cases cover canonical YouTube URLs, source identity and duration bounds, absolute caption timestamps, invalid JSON content, transcript/word/currency consistency, duplicate ranges, no full-audio download, corrected-caption caching, local caption shifting, metadata-only extraction, export records and Telegram command routing without an API key. A real Chromium fixture verified completed JSON extraction with no file attachment, and explicit signed-out detection.
- A live metadata-only extraction succeeded for the user's previously submitted YouTube URL. The subsequent live Gemini request stopped because the shared saved project profile displayed **Sign in**. No AI clip response or new Gemini clip was produced. The image-generation live check had the same session dependency; no new carousel artwork is claimed as live-validated. Current per-niche character paths exist locally.
- Automatic approval review initially blocked opening a login window because its service reported a usage limit; a later retry was approved. The user clarified that the existing project Chromium implementation must be reused. That is the final configuration; the attempted alternative Chrome attachment implementation was removed.
- No live Instagram post was published during these checks. Production publishing still depends on valid local credentials, media hosting and account availability.

See `RESEARCH_AND_UPGRADE.md`, `UPGRADE_GUIDE.md` and `FEATURES.md` for evidence, controls, configuration and limits. Older verification entries below describe earlier snapshots and should not be read as the current browser or music-library state.

Verified in this Windows workspace using the project's Python 3.12 virtual environment:

- **36 automated tests passed** (`python -m pytest -q`, 7.35 seconds on the final run).
- Ruff checks passed; `pip check` found no broken requirements.
- FFmpeg's H.264/AAC encoders and ASS, blur and loudness filters are available.
- Real FFmpeg tests exercised blur, center crop, moving crop, all three caption styles and complete output decoding.
- The synthetic `cliper demo` generated two actual 360×640 captioned MP4s.
- Windows-generated speech was transcribed with local faster-whisper `tiny` on CPU using int8 and real word timestamps.
- That transcript was selected and rendered into a **1080×1920, 15.03-second** clip with highlighted captions and normalized audio. Its output passed duration, size, audio and complete decode checks. The preview was visually inspected.
- Windows cancellation was tested, including the direct-child termination fallback when the restricted session denies `taskkill`.

Local samples:

```text
data/demo/e82a925f/clips/clip_01.mp4
data/demo/e82a925f/clips/clip_02.mp4
data/speech-demo/7a22ccd0/clips/clip_01.mp4
data/speech-demo/7a22ccd0/preview.png
```

The speech demo uses generated speech and basic offline ranking. It is not a benchmark of editorial quality on real podcasts or a claim about likely views.

At initial verification, Telegram authentication/upload/delivery, paid OpenAI inference, live provider downloads, Docker build, CUDA execution, and face tracking on real camera footage had not been live-tested. Later hardware checks are recorded below. API staging, bot handler registration, ownership enforcement and delivery recovery were tested with mocks. The included GitHub Actions workflow has not been run remotely.

## Grok and Gemini provider update

- **55 tests passed** after adding xAI Grok and Google Gemini (final run: 12.98 seconds); Ruff passed.
- Tests use the actual OpenAI Python SDK with an HTTP mock transport to verify each provider's endpoint, credential isolation, JSON Schema request, context/discovery/critique stages and final clip validation.
- Added checks for refused/truncated/malformed responses, quota errors without provider fallback, cancellation, Gemini model discovery, secret redaction, persisted Telegram switching and provider/model job snapshots.
- `doctor --provider grok` correctly resolves xAI and its configured model; CLI help includes per-run provider selection.
- Missing Grok/Gemini configuration fields were added to the local `.env` without replacing existing values. No additional dependencies were needed.
- Live Grok and Gemini inference remain unverified because their API keys are not configured. No paid provider calls were made for this update.

## RTX 4060 GPU update

- Detected NVIDIA RTX 4060 with 8188 MiB VRAM and driver 581.86. CTranslate2 detected CUDA device 0.
- Installed project-local NVIDIA CUDA 12/cuBLAS/cuDNN 9 runtime packages. The system driver and system PATH were not changed.
- Saved `WHISPER_DEVICE=cuda`, `WHISPER_COMPUTE_TYPE=int8_float16`, `GPU_DEVICE_INDEX=0` and `VIDEO_ENCODER=h264_nvenc` to `.env`, preserving Telegram and provider settings.
- Both cached `tiny` and configured `small` Whisper models completed real speech transcription on CUDA. The `small` run recorded its actual device and compute type in `data/speech-demo/fc63d9b1/transcript.runtime.json`.
- A full sample export used **h264_nvenc**, producing a **1080×1920, 18.73-second** captioned clip. Its audio, size, duration and complete decode checks passed, and the preview was visually inspected.
- Sample: `data/speech-demo/fc63d9b1/clips/clip_01.mp4`.
- **58 automated tests passed**; Ruff and `pip check` passed. `doctor` passed CUDA library/compute checks and a real NVENC encode.
- Video filtering, subtitle composition, face detection and audio processing continue to use CPU components. The supplied Docker/Compose deployment remains CPU-only; this GPU verification used the local Windows runtime.

## Demo color-bar report

- Inspected `data/demo/e82a925f/preview.png`: the bars were deliberately generated by the original `testsrc2` diagnostic source, not a corrupt GPU export.
- Default `cliper demo` now generates a designed portrait card and spoken audio, runs real transcription and exports at 1080×1920. Color bars and fixture captions require explicit `--diagnostic`. A local recording can be supplied through `--audio`.
- Ran the default command successfully using Windows speech synthesis. The restricted execution sandbox could not access the installed voice; the approved run outside that sandbox succeeded.
- New sample: `data/demo/cf1583d3/clips/clip_01.mp4`, 18.73 seconds, 826,930 bytes. Full decode, audio level, resolution and duration checks passed. Visually inspected its generated `preview.png` for caption placement and absence of test bars.
- `transcript.runtime.json` records `small`, `cuda`, `int8_float16`, device 0; export metadata records `h264_nvenc`.
- **61 tests passed** in 15.59 seconds; Ruff passed. New tests cover default speech routing, explicit diagnostic mode and keeping GPU configuration without inserting fixture transcripts or fallback tones. This is a generated speech demo, not validation of real podcast editorial quality.

## ChatGPT Chromium provider — September 9, 2026

- Added `chatgpt_browser` (`chatgpt` and `browser` aliases), Telegram switching, saved job snapshots, manual login and a JSON connectivity command. Installed Playwright 1.62.0 and its Chromium browser locally. Set the local `.env` default to `chatgpt_browser`, preserving other settings.
- Incorporated the user's browser selector/popup improvements. Live inspection identified the signed-in account control and the current `section[data-turn="assistant"]` turn container. Completion detection supports that layout and legacy articles; it does not accept a streaming pause alone as completion.
- A real website run completed source summarization, proposal discovery and editorial critique, validating each JSON envelope and the returned source segment IDs. No API client, API key or paid API fallback was used.
- Successful job: `data/jobs/80b6aa351859/`. It reused the previously verified CUDA transcript from the spoken sample, selected 0.00–18.74 seconds through ChatGPT and rendered `clips/clip_01.mp4` through the normal NVENC export/QA pipeline. This run verifies website analysis plus rendering; the earlier GPU section records the actual transcription checks.
- **77 tests passed** in 22.32 seconds; Ruff and `pip check` passed. Coverage includes real Chromium fixtures for both turn layouts, stale IDs, incomplete/invalid JSON, bounded repair, limits, cancellation, no API transport, schema references, provider switching and persisted job settings.
- Website operation remains dependent on ChatGPT's session, account limits and UI. The free provider does not guarantee unlimited availability or viral performance. Telegram delivery for this new provider was covered by existing/mocked bot tests; the live sample used the local CLI and did not send a Telegram message.

## 100% Free AI Provider & Launcher Update — 9 September 2026

- Configured `AI_PROVIDER=chatgpt_browser` as the default in `.env` along with `CHATGPT_BROWSER_TIMEOUT=240`, `CHATGPT_BROWSER_MAX_CHARS=60000`, and `CHATGPT_BROWSER_HEADLESS=false`. This enables 100% free operation with no paid API keys or API credits required.
- Added root launcher scripts:
  - `start.ps1` at the workspace root to run the bot directly with `.\start.ps1`.
  - `start.bat` at the workspace root for one-click execution from Command Prompt / Explorer.
  - `bot.py` at the workspace root for `python bot.py`.
  - `scripts/chatgpt-check.ps1` for quickly checking the saved browser session without starting a full render.
  - Made `cliper/bot.py` self-resolving with package detection so running `python bot.py` from any directory works without `ImportError: attempted relative import with no known parent package`.
- Hardened `BrowserEditorialClient` in `cliper/browser_provider.py`:
  - Ensured `PLAYWRIGHT_BROWSERS_PATH` is always initialized to `data/browsers/engines` on context startup.
  - Added `--disable-blink-features=AutomationControlled` to launch args to avoid automated browser detection on `chatgpt.com`.
  - Added `dismiss_popups` helper to auto-dismiss common ChatGPT modal banners ("Stay logged out", "Dismiss", "Got it", "Accept all", "Maybe later").
  - Enhanced selectors for `COMPOSER`, `SEND`, `STOP`, `COPY`, `USER_MENU`, and `LOGIN` to accommodate ChatGPT web interface variations.
  - Enhanced ProseMirror composer send button activation and Enter fallback.
- Test Suite & Diagnostic:
  - **76 automated tests passed** (0 failures, 0 skipped); `ruff check` passed.
  - `cliper doctor` reports all checks `[OK]`, including `[OK] AI configuration` and `[OK] Browser provider installed` with no API keys required.

## Feature 1 editing/publishing and Feature 2 carousels — September 9, 2026

- **96 tests passed in 32.91 seconds**, with no skips. Ruff and `pip check` passed. Tests include real Chromium local fixtures, real FFmpeg exports, and mocked external AI/Instagram transports.
- A real cached gaming source was rendered with the new black 1080×1920 canvas, centered 1:1 video and white hook title. Output: `data/verification/square-hook/clip_01.mp4`, 57.967 seconds, 39,385,218 bytes, **h264_nvenc**. Full decode and audio-level checks passed; `preview.png` was visually inspected. This reused a cached edit plan/transcript and does not validate newly generated AI captions or music classifications. User music folders are currently empty.
- A live selected-range download requested 1112.36–1117.36 seconds and produced `data/verification/range/range.mp4`: **5.005 seconds**, 1920×1080, with audio. A frame two seconds into the result correlated 0.9405 with the corresponding cached full-source frame, supporting range alignment. No full-video fallback was used. Audio-first orchestration and shifted caption timestamps were additionally checked with mocks.
- Real FFmpeg tests exercised square composition, caption/title separation, looped category music at 0.20 gain, carousel fitting to 1080×1350, and the swipe overlay on every slide except the last.
- Publishing tests verify owner checks, idempotent records, manual approval, actual-publication-based spacing, turning automatic publication off, Reel and ordered carousel container flows, expired-container recovery, and ambiguous/already-published outcomes that cannot be blindly retried. **No live Instagram publication was made.** Public HTTPS routing and each professional account still require the user's local configuration and live validation.
- F2 tests exercise weighted scoring and arithmetic checks before images, failed pre-image review, per-slide character attachment, visual QA, output delivery, cached retry, feature controls, persisted cancellation, and scheduled production ahead of the saved publish time. Actual Playwright Chromium fixtures verified image attachment/download and JSON review for two slides; **the live Gemini website was not tested**, and no user carousel artwork was generated because per-niche character paths and Gemini login remain to be supplied.
- The optional live ChatGPT metadata test was rejected by automatic approval review because it would transmit cached transcript text externally. It was replaced with a local-only render check; that blocked payload was not sent. Earlier live ChatGPT connectivity/analysis results above remain separate from this update.
- Current browser code removes the earlier automation-concealment launch argument recorded in the launcher-update section. Browser providers use the saved website sessions and their account limits; no paid API fallback, credential entry, or verification bypass is implemented.
- Setup and operation instructions: `FEATURES.md`. Private account/niche configs are excluded from Git and Docker context. Music folders, config templates, Gemini login script and the restricted local media server are installed. Analytics/self-learning remain excluded from v1 as requested.
