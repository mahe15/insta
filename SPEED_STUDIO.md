# IShowSpeed Studio and English-script captions

## Use the feature

Open **Speed Studio** in the web sidebar (`/speed`), paste a public YouTube video or saved stream URL, and choose **Find Speed moments**. Telegram supports `/speedclip YOUTUBE_URL`, also linked from its dashboard. The dedicated preset does not overwrite your normal clipping preferences.

Defaults: 6–60 seconds, English hooks/post captions/subtitles, square-hook layout, bold captions with up to three timed words per group, preserved wide groups, 10% BGM, 12% sound-effect gain and a subtle reaction punch-in. Duration bounds, clip count, focus timestamps, discovery budget, sound gain, music and automatic rendering are configurable. The original clip approval and Instagram publishing workflow remains in use, including two-hour spacing for automatic multi-clip jobs.

**Gemini website** is the default discovery route and uses the original shared Chromium profile. It receives the actual YouTube link, duration, editorial brief, optional focus times and a structured JSON schema. **Caption/audio discovery** uses your selected AI provider and the existing bounded long-stream scanner. If Gemini cannot access a video, the existing audio-first fallback uses that same configured provider. Partial audio scans may miss highlights; increase the budget or specify focus times. Website account limits and source availability still apply.

Review the shortlist, select clips and render, or enable automatic rendering when submitting. Each selected interval receives local caption verification. The engine downloads selected video intervals rather than the full stream. Source, range, transcript, correction, edit plan and output caches remain resumable. Silent visual moments can be selected in Speed mode without inventing dialogue; speech-based standard clipping retains its caption requirement.

## Editing decisions

The AI identifies reaction, challenge, fan encounter, football, wholesome or other moments and an optional payoff timestamp. Scoring emphasizes payoff, clarity and emotional response over educational usefulness. Instructions require the trigger, outcome and honest context, reject shouting without a story, and never turn a lost challenge into a win through misleading cuts.

| Length | Suitable complete event |
|---|---|
| 6–12 seconds | One visual gag or reaction with enough context |
| 12–25 seconds | Setup, surprise and response |
| 25–45 seconds | A challenge with its outcome |
| 45–60 seconds | A story whose context needs the time |

These are editorial options, not quotas or measured optimum durations. No duration or edit guarantees reach.

Python measures the selected interval's audio envelope in 100 ms windows. It permits at most one accent near an observed peak, within 1.5 seconds of the supplied payoff when available. Quiet/flat clips receive no accent. Wholesome and emotional-sad moments receive no comic effects or reaction zoom. A reaction can receive one 6% punch-in lasting up to 0.65 seconds; wide action framing avoids this crop. This is an audio-emphasis detector, not automatic recognition of a facial expression or a visual event.

Downloaded effects are bundled under `cliper/assets/sfx`, with a CC0 license, pinned upstream revision, source URLs and SHA-256 hashes. Reaction and reveal sounds are used by the planner; a transition sound is retained as a spare asset. Sound effects and background music are ducked beneath speech and the final mix is limited. Original speech is not replaced, sped up or rearranged. [Kenney's original pack and license](https://kenney.nl/assets/interface-sounds).

The face-track expression now uses a balanced decision tree: longer tracks no longer create a deeply nested FFmpeg expression. Portrait sources can be fitted into the square area to retain the whole picture; challenge/football shots favor full action visibility. CUDA transcription and NVENC export use the existing GPU configuration. Audio measurements and OpenCV remain lightweight CPU tasks.

## Feature 1: English letters, original spoken language

Normal clipping now defaults to **English letters · keep spoken language**. Hindi remains Hindi written with Latin letters, for example `तुम कैसे हो?` becomes `tum kaise ho?`. The original audio and evidence transcript remain unchanged. Hooks, post captions and hashtags are requested in the same script; a local romanizer enforces Latin text. Each subtitle word retains its original timestamps.

Settings → Clip & edit → **Hook & caption language** offers Romanized, English translation and Original script. The project settings dialog can override it before rendering. Speed projects always use English. Existing completed videos are not silently replaced; duplicate/re-render them to apply new text settings.

Romanization is local and requires no API. It preserves pronunciation approximately and is not a translation; spellings vary, especially for scripts with ambiguous vowels. The implementation uses [USC ISI's uroman](https://github.com/isi-nlp/uroman). Actual English translation of non-English selected speech uses the configured AI provider and is cached. Translations retain source phrase boundaries, not invented word-level phonetic alignment. Offline heuristic mode cannot translate.

## Research and evidence — October 2, 2026

Research used accessible public source pages, indexed metadata, creator documentation and a real downloaded interval. It was not an exhaustive catalog or access to private retention/share analytics. Observed popularity is confounded by the creator's audience, celebrity access and distribution; it does not establish an editing technique's causal effect.

- **Emotional meeting:** the official [IShowSpeed/Ronaldo video](https://www.youtube.com/watch?v=Fiq9XMRr4jg) is an identifiable setup/payoff example. Indexed YouTube metadata returned about 30.15 million views during research. Our real-source validation selected 18–64 seconds and visually checked frames spanning the arrival, embrace and photo moment. The implementation preserves sincere emotion and suppresses comic accents here.
- **Recognizable encounter:** [Live Speedy's Ronaldo meeting](https://www.youtube.com/watch?v=HGNUwE-wSEs) appeared in indexed metadata at about 58.81 million views. This supports investigating recognizable-person encounters; the number is an indexed snapshot, not a live analytics measurement.
- **Explicit stakes and outcome:** [Noah Lyles' original race video](https://www.youtube.com/watch?v=1SHL6zISeG0) presents a 50 m challenge against Speed. The corresponding editorial rule preserves both the challenge and result, and keeps full-body action visible.
- **Instagram cross-check:** direct access to the creator's reels page and linked reels was unavailable/rate-limited. A [third-party September 17 breakdown](https://scrptly.io/learn/ishowspeed-instagram-reels) describes four reels of 29, 31, 36 and 67 seconds, with immediate reactions and recognizable-event context. It links the [BTS encounter](https://www.instagram.com/reel/Da_i0YiCbtp/), [Ronaldo reaction](https://www.instagram.com/reel/Dad7ULhDBmo/) and [football post](https://www.instagram.com/reel/DZDCi1QxO0p/). Those posts and reported view counts could not be independently verified here. The small, selected sample supports a hypothesis about complete moments, not a universal duration rule.
- **Platform guidance:** [YouTube's conversation with Todd Sherman and Jenny Hoyos](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/) emphasizes immediate hooks and short-form storytelling. The opening rules use this as creator guidance, not an algorithm guarantee.

The profile turns these observations into rules about complete events, truthful hooks and restrained sound; it does not copy captions, music or branding from fan pages. Scores are editorial estimates, not predicted views.

## Verification and limits

`scripts/verify_speed_live.py` ran Gemini analysis through the existing session, downloaded the selected interval, performed local speech correction and exported a real 46-second 1080×1920 NVENC clip. Full decode passed, all 92 sampled content frames passed black/static checks, and measured peak audio was −1.3 dB. The final cached-selection render attempt took 22.78 seconds; this excludes earlier discovery, repair and download work and is not an end-to-end speed benchmark.

Gemini initially returned captions inconsistent with its transcript. Bounded repair requests now correct invalid responses while retaining strict validation and diagnostic copies. The actual clip still has editorial flags, including low-confidence recognition and pauses, so it needs human review. Technical QA is not proof of perfect captions or a viral clip. No verification sample was submitted for publication.

Local sample: `data/verification/speed-studio-live/clips/clip_01.mp4`. Metadata, captions, source contact sheet and measured results are beside it. Automated tests cover API isolation, duration limits, language conversion, immutable source timestamps, translation caching, sound licensing, sparse effects, real FFmpeg rendering and the browser submission workflow. See `VERIFICATION.md` for final test counts.
