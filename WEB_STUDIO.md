# CLIPER Studio

A local web workspace for the existing Python engine. Built with React 19, TypeScript, Vite, TanStack Query, Radix Dialog and FastAPI. It shares the original SQLite database, media library, configuration and Chromium profile.

## Open the studio

Double-click `studio.bat`, or run:

```powershell
.\scripts\start-web.ps1
```

Keep its terminal running. It opens `http://127.0.0.1:8788` and signs in using the local launch key. If the studio is already running, open that address instead of starting another copy. A manual login uses the contents of `data/web/access-key`; keep that key private. Click your profile at the bottom of the sidebar to lock the studio.

For a fresh checkout, install Python 3.12 and Node.js 22.12+ or 24 LTS, then run `scripts/setup-web.ps1`. The setup script bypasses broken global npm shims by invoking npm through Node directly.

## What you can control

- **X Studio:** research football, AI/technology, gaming, movies/TV, music or business; add keywords, inspect sources, attach real media, schedule research and manage the experimental browser publishing queue. See [X Studio setup and research](X_STUDIO.md).

- **Studio:** add supported video links or upload video; choose the provider, clipping route, scan budget, focus timestamps and clip count. Search and filter actual jobs, inspect progress, cancel, retry or duplicate projects.
- **Project review:** play completed clips, inspect transcript and analyzed ranges, select clips to render, edit hooks, timestamps, Instagram captions and music categories before rendering. Project editing settings override only that job. Download video, subtitles and edit metadata. Editorial scores describe model assessments, not predicted views.
- **Carousels:** generate niche posts, configure brand and content pillars, upload character references, review finished slides, and manage recurring generation schedules and time zones.
- **Publishing:** review real approval requests, edit captions, publish approved items immediately, schedule them, reject them and inspect published history. An uncertain remote publication cannot be blindly retried. Instagram still requires a configured professional account and publicly reachable HTTPS media hosting.
- **Music:** upload and preview tracks in the five existing mood categories. Tracks remain in the engine's music library.
- **Settings:** control framing, resolution, captions, titles, clip lengths, music gain and ducking, AI/provider/model choices, discovery budgets, feature switches, automatic rendering/publishing, niche availability and hardware/resource settings. Credentials are write-only and stored locally.

The interface uses warm neutral surfaces, restrained accents, local fonts, responsive layouts and keyboard-accessible dialogs. Press **Ctrl+K** (or **Cmd+K**) to search, **N** for a new project, **?** for help and **Escape** to close dialogs.

## Worker and configuration behavior

**Speed Studio** in the sidebar is the dedicated IShowSpeed YouTube workflow. It exposes 6–60 second duration bounds, discovery engines, focus times, sound effects, reaction zoom, background music and automatic rendering. Its isolated English preset retains the existing review/publishing flow. Standard clips default to Latin-script text; change **Hook & caption language** in Settings or per-project preferences. See [SPEED_STUDIO.md](SPEED_STUDIO.md) for research, usage and the real-source verification.

The web API binds to `0.0.0.0` by default so other devices on your local Wi-Fi network (such as phones or tablets) can access Studio using your computer's IP address (e.g. `http://192.168.1.60:8788/#key=...`). To restrict access exclusively to loopback, pass `-Host 127.0.0.1` to `scripts/start-web.ps1`. Session cookies, CSRF tokens, strict local/private network host validation, owner authentication checks and managed media paths protect the control plane from external websites.

One worker lock prevents duplicate engine instances. When the updated Telegram bot is running, Studio attaches to its queue. Otherwise Studio starts a worker that claims only web-origin jobs (`chat=0`). Web output is kept in the project and can enter the normal publishing flow; it is not sent to a Telegram chat. Run the bot for Telegram delivery and Telegram-origin jobs. Stop the current standalone web server before switching to a bot-owned worker.

Use `scripts/start-web.ps1 -NoEngine` to review data with workers stopped. Settings → System can start the engine or stop its local workers. An attached Telegram worker must be managed through its own process. Stopping workers retains queued work; it does not remove jobs or revoke already-sent external requests.

Preferences apply to new jobs; existing jobs retain snapshots. Per-project editing controls are available while awaiting selection. Changes to API keys or system environment settings require restarting the **server and whichever process owns the engine**, so they reload `.env`. The Start/Stop buttons alone do not reload environment configuration. Retention configuration applies to the existing maintenance path; the standalone web runtime does not run a separate retention sweep.

Automatic publishing is a real engine setting. Turning it off holds pending automatic posts for review. Starting an engine with queued publishing work or enabled schedules can process that work. Browser AI continues to use the existing shared profile and the websites' account limits; the UI does not create another profile.

## Development and verification

```powershell
.venv\Scripts\python.exe -m pip install -e '.[dev,web,browser]'
cd frontend
npm ci
npm run build
npm run format:check
cd ..
.venv\Scripts\python.exe -m cliper web --no-engine
```

For live frontend development, run `npm run dev` in `frontend` while the API is running on port 8788. Vite proxies API requests to the Python server. The production server serves `frontend/dist` and supports direct navigation to workspace routes.

`tests/test_web.py` exercises the real API with temporary storage. `tests/test_web_browser.py` launches Chromium against an isolated fixture server to test settings persistence, editorial changes, rendering selection, intake/cancellation and publication review. It needs a built frontend and installed Playwright Chromium. No external publisher is started by that test.

`scripts/verify_web_ui.py` checks the running workspace without submitting jobs or publishing. Screenshots and results are saved under `data/verification/web-studio`. See `VERIFICATION.md` for measured checks and `WEB_DESIGN.md` for the design rationale and research.
