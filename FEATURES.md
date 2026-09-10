# Feature 1 and Feature 2 setup

Start the bot with `scripts/start.ps1`, then send `/start` in your private Telegram chat. The dashboard has **F1 · Clips**, **F2 · Carousels**, **Together**, independent feature switches, AI providers, editing settings, niche switches, schedules and the publishing queue. Changing the AI provider applies to new jobs. Keep one bot process running for production and scheduled publishing.

## Feature 1: clips

For video links, CLIPER downloads audio first, transcribes it locally, and asks the selected AI to choose clips and return a title, music category, caption and up to five hashtags. It then downloads only the selected video ranges. Hosts must support ranged extraction; a failed range download produces an error instead of a full-video fallback. Local uploads already contain the video and use that local file.

The default export is a **1080×1920 black canvas**, with a centered **1080×1080 square video**, a wrapped white bold hook title immediately above it, and optional timed captions. Turning captions off keeps the hook title. Whisper uses CUDA and final video encoding uses NVENC on this machine; audio and composition still use CPU components.

Put your tracks in these existing folders:

| Folder inside `music/` | AI category |
|---|---|
| `Cinematic - Epic` | `cinematic_epic` |
| `Emotional - Sad` | `emotional_sad` |
| `Suspense - Thriller` | `suspense_thriller` |
| `Energetic - Hype` | `energetic_hype` |
| `Chill - Ambient` | `chill_ambient` |

Supported files: MP3, WAV, M4A, AAC, FLAC and OGG. One random matching track is looped beneath the speech at **20% linear volume**. A saved selection is reused on retry. Empty categories render without music; the export's JSON records the category, selected file and gain. Use the Music button or `/music on` and `/music off`.

**F1 auto-publish ON** also enables automatic rendering: the first clip is queued immediately, and subsequent clips from that job wait two hours after the preceding clip actually publishes. **OFF** gives every finished clip Publish now / Reject buttons. Turning it off holds queued automatic posts for approval. A manual approval publishes immediately, removing its scheduled delay. API processing can add a short delay. A failed predecessor holds later clips until resolved or individually approved.

Command alternative: `/autopublish on`, `/autopublish off`, `/feature f1`, `/feature f2`, `/feature both`.

## Instagram setup for both features

Local config files already exist. For a fresh installation, run `scripts/setup-features.ps1`; it preserves existing configuration.

1. In `config/instagram.json`, fill the professional Instagram **numeric user ID** and your numeric Telegram ID in `owners`, for each account you use. `clips` is F1; `dark`, `men`, `money`, `tech` and `finance` are separate F2 account mappings. Obtain your Telegram ID with `/whoami`.
2. Put access tokens only in `.env`, using the variable referenced by each `token_env`, such as `IG_CLIPS_TOKEN` or `IG_DARK_TOKEN`. Select `login: "instagram"` for Instagram Login tokens or `"facebook"` for Facebook Login tokens. Use the appropriate permissions for that login flow; Facebook Login also needs its linked Page. See [Meta's official API documentation](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).
3. Set `PUBLIC_MEDIA_BASE_URL` to the public HTTPS address serving `PUBLIC_MEDIA_DIR` (default `data/public-media`). Meta fetches the finished media from these URLs. You can serve that directory with:

   ```powershell
   .\.venv\Scripts\python.exe -m cliper serve-media --host 127.0.0.1 --port 8787
   ```

   Route your existing HTTPS reverse proxy to this port. For a URL such as `https://media.example.com/cliper`, the proxy must strip `/cliper` before forwarding. Keep the media server running alongside the bot. It exposes only staged MP4/JPEG assets, with no directory listing. Files are staged locally; CLIPER does not automatically upload them to a separate remote host. Use a mounted/synced directory if your HTTPS hosting is elsewhere.
4. Restart the bot after editing `.env` or credentials. Generate an item with auto-publish off and use Publish now for your first real account test.

Example account entry (replace the example IDs):

```json
"dark": {
  "ig_user_id": "17840000000000000",
  "token_env": "IG_DARK_TOKEN",
  "login": "instagram",
  "owners": [123456789]
}
```

The publisher persists media containers and resulting Instagram media IDs. Failed preparation can be retried from the queue. An interrupted/ambiguous publish is marked **uncertain** and cannot be resent automatically; inspect the Instagram account before resolving it. This avoids duplicate posts. Expired containers are recreated on an explicit retry. Automatic token renewal and remote hosting setup are not included.

## Feature 2: faceless carousels

Each niche has its own brand, pillars, banned topics, character reference and Instagram account. Fill `character_path` in `config/niches.json` for the niches you want to enable. Use an absolute path with forward slashes, for example `C:/Characters/dark.jpeg`. Leave other niches disabled until their images are ready. No example character is substituted for a missing image.

Sign into Gemini once using its separate saved Chromium profile:

```powershell
.\scripts\gemini-login.ps1
```

Sign in yourself, wait for the Gemini composer, then close the window. Reasoning uses your selected ChatGPT website/OpenAI/Grok/Gemini provider. **Images always use the Gemini website through Playwright**, with the relevant character reference attached for every slide. The offline heuristic provider supports F1 only. Website adapters have no API-key requirement; their account limits and UI availability still apply. See [Gemini's image-generation help](https://support.google.com/gemini/answer/14286560?p=b_gen_img).

In Telegram, enable F2, select and enable a niche, then choose **Generate carousels** and a count. `/generate N` also supports any count from 1 to 20.

Production steps:

1. Gather configured RSS headlines for topic discovery and load recent content history. If feeds are unavailable, use an explicitly marked evergreen brief.
2. Generate three distinct candidate ideas per requested carousel. Score hook 25%, share 20%, save 20%, emotion 15%, novelty 10%, audience 5% and brand 5%. Select only candidates meeting the configured threshold, default **90/100**.
3. Write a 4–7-slide script and run a separate pre-image content review. Validate supplied arithmetic expressions. A failed review stops image generation.
4. Gemini generates each complete image, including typography. Gemini then checks the image against the reference and intended text. Failed image QA stops publication.
5. FFmpeg fits each slide to **1080×1350** and adds the small bottom-right swipe overlay to all slides except the last. Send the carousel to Telegram and create its publication record.

Scores and AI visual checks are editorial filters, not guaranteed reach or perfect factual/visual verification. Headline discovery does not verify article claims. Plans, scores, research, QA, images and delivery markers are saved under `data/carousels/JOB/`. Retry reuses successfully checked slides; Regenerate creates a new job. Analytics and self-learning are excluded from v1 as requested.

F2 auto-publish has its own switch (`/autopublish on f2` or `/autopublish off f2`). Automatic posts for the same niche account have a three-hour minimum gap after the preceding successful publication. Approval mode provides Publish now / Reject buttons.

## Scheduling and recovery

Select a niche, then Schedules. Buttons provide every 3/12/24 hours, daily 8 PM IST, Monday/Wednesday/Friday 8 PM IST, or Off. The 12-hour choice supports two posts per day. Custom daily schedules use `/schedule 20:00 Asia/Kolkata`; optional weekdays: `/schedule 20:00 America/New_York mon,wed,fri`. There is one recurring schedule per owner and niche; saving another replaces it.

Scheduled production begins up to one hour before its target time. Auto-publish waits until that time and respects the account's minimum gap. In approval mode it waits for you. Generation taking longer than the lead time, account limits, an earlier failed post, downtime or API processing can delay publication. Missed schedules do not create a catch-up burst. Schedule Off stops future generation; review existing items in the publishing queue separately.

Feature/niche OFF pauses production and prevents pending automatic posts from being published without approval. Cancel stops a generation job; existing finished publications remain separately controllable. Restart resumes unfinished production and retains queued/approved publications. Keep character images, source files and staged media available for retries. Local config, tokens, browser profiles and generated media are excluded from Git.
