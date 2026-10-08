# X Studio

Open **X Studio** in CLIPER's sidebar, or `http://127.0.0.1:8788/x`. It researches current stories through the existing ChatGPT Chromium session, writes English posts, attaches real media and maintains a durable review/publishing queue. It does not generate images or videos and does not require an X or AI API key.

## Editorial research and decisions

Research checked on October 3, 2026. There is no defensible universal ranking of the six “most viral” categories. The starting desks are football, AI/technology, gaming/esports, movies/TV, music, and business/finance. They cover established conversation communities in [X's historical 2024 topic report](https://business.x.com/en/blog/buckle-up-advertisers-2024-on-x-was-good-for-business); that report is historical platform marketing data, not a forecast of your account's reach.

[X's organic posting guide](https://business.x.com/content/dam/business-twitter/resources/x-downloadable-guides/build-your-presence-on-x-one-sheet.pdf) recommends audience-relevant subjects, a natural voice and photo/video attachments. [Its World Cup report](https://blog.x.com/en_us/topics/events/2022/2022-World-Cup-Insights) illustrates how major live football moments concentrate conversation. Our editorial inference: prioritize a fresh, specific development and explain one useful consequence; do not turn every headline into exaggerated breaking news.

[X's published recommender repository](https://github.com/xai-org/x-algorithm) describes personalized retrieval, predicted viewer actions and visibility filtering. It explicitly warns that action weights apply to predicted probabilities, not raw engagement counts. Consequently, CLIPER does not invent a “viral algorithm score,” guaranteed reach, universal posting hour or fixed like-to-repost multiplier. Its hook, clarity and sourcing scores are model assessments for review. They are not measured performance predictions.

| Desk | Useful editorial angle | Evidence to seek |
| --- | --- | --- |
| Football | A match turning point, tactical change or confirmed transfer and its consequence | Club/league statement and independent reporting; exact match/date |
| AI & technology | What changed, who can use it, and a concrete limitation | Official release notes and independent examination |
| Gaming & esports | A patch's practical effect, an official release, tournament result | Developer/tournament announcement and corroboration |
| Movies & TV | A confirmed release/casting update or craft observation | Studio/creator source; avoid spoilers and rumors |
| Music | Release/performance news or a specific craft observation | Artist/label source; verify chart claims and avoid copied lyrics |
| Business & finance | A dated company development and understandable implication | Filing/company announcement plus reporting; no price predictions |

The six categories are options, not a recommendation to mix unrelated subjects on one account. Choose a coherent audience. Short, clear text and accurate media are initial editorial choices to evaluate with your own results, not a guarantee of virality.

## First use

1. Let any current ChatGPT/Gemini job finish. Run `scripts/x-login.ps1` from PowerShell. It opens X in **the same** `data/browsers/chatgpt-profile` used by the existing browser providers. Sign in manually and close the window. Never send passwords to the bot.
2. Open **Account & automation**, enter the exact X username, and review the browser-publishing notice. The username is checked against X's visible profile link before every submission. Entering a username alone does not prove the browser is signed in.
3. Choose a category, optional keywords, post style and freshness window. Click **Research a post**. For example, football + `Arsenal midfield tactics`, or technology + `new developer tools`.
4. Open the completed draft. Inspect the original source links, dates, claims, text and attachment. Upload your own authorized image/video if the photo search found no suitable media. Confirm review and queue immediately or choose a time.
5. For recurring work, choose a 3–168 hour research cadence and **Schedule this topic**. One schedule per category is stored. The first scheduled run is after that interval; use **Research a post** for an immediate first draft.

The local Studio/Telegram engine must remain running for schedules and publication. Missed intervals create at most one fresh research job per schedule, not a burst of old posts. The queue shares CLIPER's existing engine lock; only one engine should run. Browser work waits when the shared profile is busy.

Telegram also supports `/xpost football Arsenal tactics` and `/xjobs`. These commands are restricted to configured owners in private chats. Source review, media, account settings and publication controls are in the web Studio. CLI login is also available as `.venv/Scripts/python.exe -m cliper x-login`.

## Research and media pipeline

```text
Category + keywords + explicit UTC freshness cutoff
  → ChatGPT website: search web, open original sources, cross-check latest updates
  → schema-validated research, dates, claims, uncertainty and visible citation URLs
  → bounded retry for stale/invalid dated research
  → separate English writing pass using that evidence
  → primary source URL + real-media attachment
  → review, or automatic eligibility checks
  → durable schedule → exact X account check → upload → single submission
  → confirmation URL, or uncertain state requiring inspection
```

The research schema requires two sources. Automatic eligibility also requires two distinct source domains, a primary source, known publication dates, matching visible ChatGPT source links, no reported uncertainty, editorial score thresholds, and a relevant preapproved category attachment. These checks cannot independently establish that every claim is true: source classification and paraphrases still come from ChatGPT. Inspect the originals for consequential claims. If ChatGPT Search is unavailable, a login/challenge appears or a usage limit is reached, the job stops with an error instead of inventing a publishable result.

Newly discovered photographs come only from Wikimedia Commons with CC0/public-domain metadata. The downloader only fetches the Wikimedia upload host, checks size and decodes the image. These photos **always need human relevance/context review**. A search result is not proof that an image depicts the current event. License/source/creator metadata is retained. If nothing suitable is found, the draft waits for an uploaded attachment.

**Manage category media** stores real images or videos you own or have permission to publish. Describe exactly what they show. The latest attachment in the selected category is offered to the writing pass, which must judge its described relevance. Reusable media is labelled illustrative. For a different person, team or event, replace the attachment and review the exact post. Removing a library entry stops future reuse but preserves immutable files referenced by existing posts.

CLIPER's conservative upload limits are JPG/PNG up to 5 MiB and H.264 MP4 up to 80 MiB, 140 seconds and 1920 pixels on the longest side. Videos are decoded with FFmpeg before acceptance. These are application limits, not a complete statement of X's account-dependent upload rules. No third-party highlight video is automatically downloaded or reposted. Finished CLIPER MP4 exports can be uploaded when you have publishing rights.

## Automation behavior

All X publication is **off by default**, including the approval button. Research and draft editing remain available. When ready, configure the username, choose browser publishing and turn on **Enable X publishing**. Turning it off holds both manual and automatic queued posts and prevents submissions, including after browser preparation. For automatic posting, also upload suitable category media and turn on **Publish automatically**. Flagged research or unreviewed new photos still wait for review. Defaults are four submission attempts per rolling 24 hours, at least 120 minutes apart and a 24-hour freshness window. These are conservative starting controls, not claimed optimal posting times.

The engine checks both research age and event age again before publication, including after waiting in the queue. Delays can therefore make a scheduled item stale. Research a fresh post rather than posting outdated news. Turning off automatic publishing holds queued automatic posts for review. Changing the account invalidates queued approvals. Pausing the X engine leaves other CLIPER features running; in-flight research may finish, but the publisher rechecks pause/account settings before submission.

Exact normalized text and previously used primary story URLs help prevent duplicate posts. There are no automated likes, follows, replies, DMs or unsolicited mentions. Standard post text is conservatively limited to 280 weighted characters, with URLs counted as 23, and at most two hashtags.

Submission intent is persisted before clicking Post. If the browser disconnects afterward, the job becomes **Check X first** and is never automatically retried. Inspect the actual account; if it was posted, enter its real post URL to reconcile the queue. This avoids a second post after an ambiguous timeout. A browser layout change may require selector maintenance.

**Platform limitation:** [X's automation rules](https://help.x.com/en/rules-and-policies/x-automation), updated April 2026, prohibit scripting its website and warn that this can lead to permanent suspension. This requested Playwright integration is experimental; review mode remains available without enabling browser publication. It does not bypass challenges or rate limits.

## Files and verification

- `cliper/x_content.py`: research schema, prompts, evidence checks and real-photo retrieval.
- `cliper/x_studio.py`: SQLite state machine, schedules, media references and worker.
- `cliper/x_browser.py`: shared-profile account verification, composer, attachment and submission.
- `cliper/x_web.py`: authenticated/CSRF-protected endpoints and validated uploads.
- `frontend/src/XStudio.tsx`: research, library, review, schedules and account UI.
- `tests/test_x_studio.py`: state transitions, stale evidence, owner isolation, uploads, scheduling, profile reuse and Chromium composer fixtures.
- `scripts/verify_x_live.py`: optional real ChatGPT research check; saves local verification output and **never publishes**.

Automated tests use an intercepted Chromium X fixture, not a live X account. Desktop/phone checks are saved under `data/verification/web-studio/x-studio-*.png`. On October 5, 2026, live ChatGPT research completed and produced an English football draft with source URLs. The result correctly remained review-only because of reported uncertainties and incomplete visible citation corroboration; no suitable CC0/public-domain image was found for that specific query. Nothing was published. The primary squad update was also checked against the original England Football page.

That real run led to two additional fixes: URL matching now ignores attribution tracking tags while preserving article-identifying query parameters, and citations from the first browser response survive a JSON repair. The required full-URL prompt also explicitly excludes internal citation tokens from JSON URL fields. The latest focused regression run passed 48 tests; the preceding complete run passed 261 tests and exposed one outdated Telegram-handler-count assertion, which was replaced with command-registration checks and passed on rerun. The production frontend builds successfully, dependencies check cleanly, and desktop/mobile checks reported no page errors or horizontal overflow. Live X submission still needs the intended account/login and an approved real post; it has not been verified on a real X account.
