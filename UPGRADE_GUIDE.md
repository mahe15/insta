# Studio upgrade guide

Restart the bot with `scripts/start.ps1` after stopping the old process with Ctrl+C. Keep only one bot process running. Send `/start` to get the updated dashboard. Existing credentials, character mappings and saved preferences are retained; new fields receive their model defaults.

## September 27 long-stream upgrade

The local configuration now permits 24-hour sources and the expanded platform list. New normal-link jobs use captions or budgeted audio scans. Existing completed jobs keep their existing analysis; submit a new job to use the new route. `/scan 24`, `/scan 60` and `/focus HH:MM:SS` control discovery. Partial coverage is explicit, and `/focus clear` removes timestamps before an unrelated source. Full details and references are in [LONG_STREAM_ARCHITECTURE.md](LONG_STREAM_ARCHITECTURE.md).

YuNet is installed and hash-verified on this machine. On another machine, install current project dependencies with `python -m pip install -e '.[gpu,browser]'`, then run `python -m cliper.face_model`. The downloader now includes its curl-cffi extra for Kick. `FACE_MODEL_PATH`, `LONG_SOURCE_MINUTES` and `SCAN_DOWNLOAD_WORKERS` are documented in `.env.example`. No Chromium profile migration or new login setup is part of this upgrade.

## Clipping improvements

- The white hook stays directly above a filled 1:1 video on the vertical black canvas. Smart crop follows detected face groups. **Preserve wide groups** is optional: it fits a wide shot inside the square when a detected group would otherwise be cut off. This is face detection, not active-speaker recognition.
- Shortlists contain three proposed hook alternatives and a **Review hook / quality** button. Select an alternative before rendering. Local checks catch invented numbers, dense titles, repeated speech, low transcript confidence, long pauses and context-dependent openings. These are heuristics, not a probability of going viral.
- Safe edge trimming removes only excess leading/trailing time when the result still fits the selected duration. Sentence-aware caption groups reduce awkward persistence. There are no automatic internal jump cuts that could change meaning.
- Music is normalized before 20% gain, with fades and optional speech ducking. Editing controls also offer 10% and 15%. Empty categories still work without music.
- Quality checks decode the entire export, check dimensions/duration/audio and sample the video content for black/static intervals. Intentional still shots are reported for review. Almost entirely black output is rejected. Each render saves a suggested cover JPEG.
- Render caches include the source, actual clip details, transcript, music inventory, face model and editing settings. Remote analysis uses captions or bounded audio windows; later extraction downloads selected video ranges.

## Faceless carousel improvements

- Five niche briefs specify audiences, visual direction and recurring post formats. Ideas compete against recent content and favor variety across pillars.
- Plans use 4–7 slides with a clear opening, useful progression and payoff. Python rejects excessive text, exact repeated slides, recent repeated hooks and unsupported research attribution before generating images. Arithmetic checks reject invalid, complex and unbounded results.
- Each slide prompt includes the full story, current slide text, character reference, camera/action/environment, readable type guidance and swipe-overlay space.
- Image checks reject nearly blank images, a returned reference instead of a new image and near-identical previous slides. Gemini's visual review must transcribe the generated text; Python checks it against the planned wording. One image correction attempt is allowed. Final posts include a local contact sheet.
- `CLIPER_SKIP_IMAGE_QA=false` is the default. Explicitly skipping QA records that fact and forces manual publishing approval.

## Reliability improvements

Telegram uploads have bounded concurrency and are cancelled with their owning job. Publication staging hashes approved media and refuses changed assets. Rejected intermediate posts no longer strand later posts, while automatic spacing still follows the last applicable successful publication. Ambiguous publication results remain blocked from automatic retries to avoid duplicate posts.

Gemini clipping is described in [FEATURES.md](FEATURES.md#clipping-using-gemini). It offers link-first analysis with optional selected-range GPU caption correction. It inherits the same Gemini browser adapter used by Feature 2 and shares the project's existing `data/browsers/chatgpt-profile` with ChatGPT. Browser work uses the existing profile lock. No separate profile, Chrome attachment setup or additional browser installation is required.

## Evidence and limits

Read [RESEARCH_AND_UPGRADE.md](RESEARCH_AND_UPGRADE.md) for the cited research and the distinction between platform statements, observational benchmarks and editorial recommendations. No duration or hook formula guarantees reach. Analytics/self-learning remain outside the requested v1 scope. Browser tests against local fixtures cannot establish that a live account is currently signed in; the live Gemini session still needs login validation. Instagram publishing still needs a real account/media-host test.
