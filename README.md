# CLIPER

> **The Autonomous AI Short-Form Video & Multi-Platform Content Studio**  
> *Turn long YouTube videos, 24-hour livestreams, podcasts, and local footage into viral, perfectly reframed vertical shorts (1080p @ 60fps), automated Instagram Carousels, and X (Twitter) viral research posts — with zero-cost browser AI or premier API providers, and direct multi-account publishing to YouTube Shorts and Instagram Reels.*

---

## Table of Contents

- [Overview & What CLIPER Does](#overview--what-cliper-does)
- [System Architecture & Pipeline Flow](#system-architecture--pipeline-flow)
- [Key Features & Upgrades](#key-features--upgrades)
  - [1. Native YouTube Shorts Publishing & Auto-Scheduling](#1-native-youtube-shorts-publishing--auto-scheduling)
  - [2. Modern Web Studio Workspace](#2-modern-web-studio-workspace)
  - [3. Zero-Cost Browser Automation (No API Key Required)](#3-zero-cost-browser-automation-no-api-key-required)
  - [4. IShowSpeed Studio & Energy Detection](#4-ishowspeed-studio--energy-detection)
  - [5. X (Twitter) News Research & Drafting Studio](#5-x-twitter-news-research--drafting-studio)
  - [6. Faceless 5-Niche Instagram Carousels](#6-faceless-5-niche-instagram-carousels)
  - [7. Next-Gen Editing Pipeline (1080p @ 60fps, YuNet, NVENC)](#7-next-gen-editing-pipeline-1080p--60fps-yunet-nvenc)
  - [8. Curated 64-Track Music Library & Dynamic Speech Ducking](#8-curated-64-track-music-library--dynamic-speech-ducking)
  - [9. Unified AI Prompt Registry](#9-unified-ai-prompt-registry)
- [Quick Start on Windows](#quick-start-on-windows)
  - [Hardware & Software Prerequisites](#hardware--software-prerequisites)
  - [Option A: Launch Web Studio (1-Click)](#option-a-launch-web-studio-1-click)
  - [Option B: Launch Private Telegram Bot](#option-b-launch-private-telegram-bot)
  - [Option C: Render a Local Demo (No Credentials Needed)](#option-c-render-a-local-demo-no-credentials-needed)
  - [System Health Check (`cliper doctor`)](#system-health-check-cliper-doctor)
- [Web Studio Guide](#web-studio-guide)
  - [Project Dashboard & Intake](#project-dashboard--intake)
  - [Interactive Clip Editor](#interactive-clip-editor)
  - [Batch "Schedule All" to YouTube with Live-Clip Skipping](#batch-schedule-all-to-youtube-with-live-clip-skipping)
  - [Mobile & Tablet Access over Local Network](#mobile--tablet-access-over-local-network)
  - [Studio Keyboard Shortcuts](#studio-keyboard-shortcuts)
- [Publishing & Distribution Hub](#publishing--distribution-hub)
  - [YouTube Data API v3 Multi-Account Setup](#youtube-data-api-v3-multi-account-setup)
  - [Native YouTube Scheduled Uploads (`publishAt`)](#native-youtube-scheduled-uploads-publishat)
  - [Instagram Graph API Setup (Reels & Carousels)](#instagram-graph-api-setup-reels--carousels)
  - [Public Media Staging Server](#public-media-staging-server)
  - [Publishing Queue Lifecycle](#publishing-queue-lifecycle)
- [AI Providers & Selection Engines](#ai-providers--selection-engines)
  - [Zero-Cost Website Adapters (ChatGPT & Gemini)](#zero-cost-website-adapters-chatgpt--gemini)
  - [Official API Providers (OpenAI, xAI Grok, Gemini API)](#official-api-providers-openai-xai-grok-gemini-api)
  - [Offline Heuristic Engine](#offline-heuristic-engine)
  - [Dynamic Provider Hot-Switching](#dynamic-provider-hot-switching)
- [Editing Pipeline & Video Engineering](#editing-pipeline--video-engineering)
  - [Layouts: Square Hook vs. Full Vertical](#layouts-square-hook-vs-full-vertical)
  - [Smart Face Tracking (OpenCV YuNet)](#smart-face-tracking-opencv-yunet)
  - [Whisper Word Timestamps & Subtitle Typography](#whisper-word-timestamps--subtitle-typography)
  - [Language Modes & Romanization (Hinglish)](#language-modes--romanization-hinglish)
  - [Color Grading & HDR-to-SDR Tone Mapping](#color-grading--hdr-to-sdr-tone-mapping)
  - [Hardware Acceleration (NVIDIA NVENC & CUDA)](#hardware-acceleration-nvidia-nvenc--cuda)
  - [Dual Export Architecture (Master vs. Telegram Compact)](#dual-export-architecture-master-vs-telegram-compact)
- [Music Library & Audio Processing](#music-library--audio-processing)
  - [The 64-Track Royalty-Free Catalog](#the-64-track-royalty-free-catalog)
  - [Automated Speech Ducking & EBU R128 Loudness](#automated-speech-ducking--ebu-r128-loudness)
  - [Custom Track Uploads](#custom-track-uploads)
- [CLI & Script Reference](#cli--script-reference)
- [Telegram Bot Commands](#telegram-bot-commands)
- [Configuration Reference (`.env` & `config/`)](#configuration-reference-env--config)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Repository Map](#repository-map)

---

## Overview & What CLIPER Does

**CLIPER** is an end-to-end autonomous content creation suite engineered for creators, clipping agencies, and faceless media operators. It transforms hours of unstructured video content into polished, engaging short-form assets formatted for **YouTube Shorts**, **Instagram Reels**, and **TikTok**, and publishes them on your terms.

### Core Capabilities

- **Intelligent Long-Stream & VOD Clipping**: Ingests videos from **YouTube, Twitch, Kick, Vimeo, Facebook, Instagram, TikTok, X/Twitter, Dailymotion, Rumble, Bilibili, and Odysee**, or local files. Handles broadcasts up to **24 hours** using captions-first indexing and bounded audio-window discovery without downloading multi-gigabyte source files.
- **Direct Multi-Account YouTube Publishing**: Connect multiple YouTube channels via OAuth 2.0, publish immediately, or schedule an entire batch of clips directly on YouTube with automatic spacing (e.g., every 2 hours) using native YouTube server-side scheduling (`publishAt`). Smart detection automatically skips clips already live on YouTube.
- **Direct Instagram Publishing**: Official Meta Graph API integration supporting multiple accounts for both video Reels (Feature 1) and multi-slide Carousels (Feature 2).
- **Zero-API-Cost Browser Operation**: Features built-in Playwright automation for **ChatGPT Web** (for narrative analysis, candidate discovery, and critique) and **Google Gemini Web** (for direct YouTube link selection and carousel slide image rendering) — zero API charges, zero API keys required.
- **Pro-Grade Production Standards**: Exports **1080×1920 at 60 fps** using NVIDIA NVENC hardware acceleration, OpenCV YuNet neural face tracking, EBU R128 loudness normalization, automatic background music ducking beneath speech, custom font rendering, and pixel-fitted animated captions.
- **Multi-Script & Romanization Engine**: Automatically transliterates non-Latin spoken languages into clean Latin characters (e.g., Hindi speech into readable Hinglish) while preserving spoken audio and verbatim timestamps.
- **Two Complete Operating Environments**:
  - **Local Web Studio**: A responsive React 19 + TypeScript + Vite workspace (`http://127.0.0.1:8788`) with live video playback, millisecond-precision trimming, hook headline tuning, prompt editing, and publishing queues.
  - **Private Telegram Bot**: An encrypted remote-control studio with inline button dashboards, interactive approvals, job monitoring, and subtitle/edit-data exports.

---

## System Architecture & Pipeline Flow

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SOURCE INGESTION                                     │
│  Public URL (YouTube, Twitch, Kick, etc.) OR Local File Upload (Web Studio / Telegram) │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DISCOVERY & TIMELINE SCAN                                 │
│  - Video Links: Captions-first indexing OR Bounded audio windows (6–1440 min budget)  │
│  - Gemini Browser: Direct link analysis in Chromium session (No video download needed) │
│  - Missing Windows: Shared local CUDA Whisper model pass                               │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         AI SELECTION & EDITORIAL CRITIQUE                              │
│  Provider: ChatGPT Browser | Google Gemini | xAI Grok | OpenAI | Heuristic             │
│  - Narrative Summarization → Candidate Moment Discovery → Editorial Critique          │
│  - Evaluates: Hook (25%), Payoff (25%), Standalone Clarity (25%), Emotion (10%), Use (15%)│
│  - Grounded Hook Generation + Deduplication + Timestamp Boundary Refinement            │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            TARGETED RANGE EXTRACTION                                   │
│  - Downloads ONLY the selected video & audio ranges (saves bandwidth & disk space)     │
│  - Local faster-whisper CUDA pass for precise word-level subtitle alignment            │
│  - Language Processing: Romanization (Hinglish/Latin) OR AI English Translation        │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              STUDIO VIDEO RENDERING                                    │
│  - Layout: 1080x1080 Square Video on 1080x1920 Canvas (9:16) with Bold White Hook     │
│  - Face Tracking: OpenCV YuNet samples faces @ 2 fps with smoothing & deadband hold    │
│  - Subtitles: ASS word-level highlights (Mint Studio, Yellow Bold, or White Minimal)   │
│  - Audio: 64-track Mood Library, 20% gain, automated speech ducking, EBU R128 norm     │
│  - Video Engine: H.264 NVENC P6/HQ CQ19 @ 60 fps + HDR-to-SDR BT.709 Tone Mapping     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          TECHNICAL QUALITY ASSURANCE (QA)                              │
│  - Full file decode verification, dimension checks, audio presence, silence detection   │
│  - Dual Export: High-Quality Master (unconstrained) + Telegram Compact delivery copy   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        DISTRIBUTION & MULTI-ACCOUNT PUBLISHING                         │
│  - YouTube Shorts: Instant upload OR direct scheduled release via native publishAt     │
│  - Instagram Reels: Automated spacing (2h gap) OR manual approval inbox                │
│  - Telegram Delivery: Video clip + downloadable SRT/ASS + edit-metadata ZIP            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features & Upgrades

### 1. Native YouTube Shorts Publishing & Auto-Scheduling

- **Official YouTube Data API v3 Integration**: Authenticate and publish directly to YouTube Shorts without third-party services.
- **Multi-Account OAuth Management**: Configure multiple YouTube channel profiles (e.g. `main`, `gaming`, `podcast`, `clips`) in `config/youtube.json`. Authorize accounts via an in-browser OAuth popup (`/api/youtube/auth-url` → `/api/youtube/callback`) or via CLI (`scripts/youtube-auth.ps1`).
- **Channel Dashboard & Profile Fetching**: Automatically pulls channel avatars, verified titles, subscriber counts, and video counts.
- **Batch "Schedule All" with Custom Gaps**: Schedule an entire project's rendered clips in one click. Define spacing intervals (e.g., 2 hours, 4 hours) and choose:
  - **Direct YouTube Scheduling**: Uploads immediately with `privacyStatus: private` and an RFC 3339 `publishAt` timestamp. YouTube automatically switches the Short to public at the scheduled moment!
  - **Local Queued Scheduling**: Holds videos in CLIPER's persistent SQLite publication queue and uploads when due.
- **Smart Live-Clip Detection**: The scheduler checks previously published records and **automatically skips clips that are already live on YouTube**, preventing duplicate uploads and conserving your daily YouTube API quota.
- **Automatic Hashtag Optimization**: Automatically injects `#Shorts`, `#Viral`, and `#Clips` into titles and descriptions if not already present.

### 2. Modern Web Studio Workspace

- **Built with Modern Web Standards**: React 19, TypeScript, Vite, TanStack Query, Radix Dialog, Lucide icons, and a custom CSS design system with sleek dark mode aesthetics.
- **Comprehensive Project Inspection**:
  - Synchronized video player with seeker and poster preview.
  - Interactive clip trimmer: modify start/end timestamps down to milliseconds.
  - Live hook headline editor and caption/hashtag modifier.
  - Niche and music category overrides per clip.
  - Full transcript viewer with word-level confidence metrics and search.
  - Visual scan coverage map displaying analyzed stream segments.
- **Network Accessibility**: Binds to `0.0.0.0:8788` by default so you can access the studio from your smartphone, iPad, or laptop on the same local Wi-Fi network. Protected by CSRF tokens, session cookies, and private launch keys.

### 3. Zero-Cost Browser Automation (No API Key Required)

- **ChatGPT Website Adapter (`chatgpt_browser`)**: Uses Playwright and an isolated Chromium profile (`data/browsers/chatgpt-profile`). Sends transcripts to ChatGPT Web, extracts structured JSON, auto-repairs schemas via `json_repair`, and returns approved candidate moments — with **$0 in API charges**.
- **Gemini Website Browser Clipping (`gemini_browser`)**: Ingests YouTube URLs directly through Google Gemini Web. Gemini analyzes the video directly without requiring local downloads. Clips, hooks, ratings, and timed phrases are extracted seamlessly.

### 4. IShowSpeed Studio & Energy Detection

- **Dedicated High-Energy Workflow**: Tailored for streaming icons like IShowSpeed, Kai Cenat, and gaming broadcasts.
- **Tight Duration Bounds**: Optimized for complete 6–60 second moments.
- **Audio Energy Envelope Analysis**: Measures audio volume in 100 ms windows to locate emotional peaks, loud reactions, and surprise triggers.
- **Subtle Reaction Zoom & SFX Accents**: Automatically inserts CC0-licensed sound effects (reaction, reveal, transition from Kenney's interface sound library) and applies a smooth 6% punch-in zoom for 0.65s near detected energy peaks.
- **Emotional Sincerity Guard**: Suppresses comedic sound effects and zooms on genuine, wholesome, or emotional moments.

### 5. X (Twitter) News Research & Drafting Studio

- **6 Conversation Desks**: Football, AI & Technology, Gaming & Esports, Movies & TV, Music, Business & Finance.
- **Real-Time Fact Sourcing**: ChatGPT Web browses the live internet, finds two independent source links, extracts dates, checks latest developments, and flags factual uncertainty.
- **Wikimedia Commons CC0 Photo Integration**: Automatically searches public-domain photographs, checks image dimensions, and downloads compliant media.
- **Owned Media Library**: Upload and tag your own images/videos for each category desk.
- **Compliance Guard**: Strictly adheres to 280-weighted-character limits and duplicate-post prevention rules.

### 6. Faceless 5-Niche Instagram Carousels

- **5 Pre-Configured Niches**: Dark / Stoicism, Men's Growth, Money & Business, Tech / AI, Personal Finance.
- **Split-Scene Visual Architecture**: Each 1080×1350 slide features a vertically stacked contrast pair (Top: Problem/Sacrifice, Bottom: Reward/Transformation).
- **Consistent Character Art**: Uses Google Gemini Web + Playwright to generate slide illustrations featuring your custom character reference image.
- **Automated Visual QA**: Gemini transcribes text from the generated images to verify spelling, currency symbols, and numbers against the editorial plan. Defective slides trigger an automatic re-render attempt.
- **Swipe Overlay & Packaging**: Adds subtle swipe-left indicators to all slides except the finale.

### 7. Next-Gen Editing Pipeline (1080p @ 60fps, YuNet, NVENC)

- **Master Output Standard**: 1080×1920 vertical canvas at a smooth 60 fps.
- **Layout Precision (`square_hook`)**: Centers a 1080×1080 video on the 9:16 canvas. The hook title is mathematically positioned immediately above the video frame, with pixel-measured margins.
- **YuNet Neural Face Tracking**: OpenCV YuNet tracks speaker faces twice per second, applying deadband smoothing, dropout hold, and scene-cut resets to ensure the subject remains centered.
- **Wide-Group Preservation**: Optional setting to prevent aggressive cropping when multiple speakers or interview guests are on screen.
- **Color Grading & Tone Mapping**: Built-in Natural and Vivid color grades, plus automatic HDR (PQ/HLG) to SDR BT.709 tone mapping.
- **Hardware Acceleration**: High-performance NVIDIA NVENC H.264 encoding with lookahead and adaptive quantization, paired with CUDA-accelerated `faster-whisper`. CPU fallback (`libx264`) available for all platforms.

### 8. Curated 64-Track Music Library & Dynamic Speech Ducking

- **64 Royalty-Free Background Tracks**: Organized across 6 mood categories:
  - `Energetic - Hype` (Drift Phonk, Brazilian Phonk, Memphis Phonk, Sigma male themes, High-energy EDM, Bluegrass country)
  - `Chill - Ambient` (Lo-Fi Jazz Lounge, Acoustic Pop, Elevator meme, chill vlog)
  - `Cinematic - Epic`
  - `Emotional - Sad`
  - `Suspense - Thriller`
  - `Phonk`
- **Dynamic Speech Ducking**: Automatically ducks background music volume beneath spoken dialogue, restoring music level during pauses.
- **EBU R128 Loudness Compliance**: Mixes speech and music with `loudnorm=I=-16:TP=-1.5` so audio sounds clear and punchy on mobile speakers.
- **Custom Uploads**: Upload MP3, WAV, M4A, or FLAC tracks directly in Web Studio.

### 9. Unified AI Prompt Registry

- Centralized prompt registry in `cliper/prompts.py` and `config/prompts.json`.
- Customizable system prompts with live reset buttons for:
  - Carousel Planning & Narrative Design
  - Carousel 10 Core Design Rules
  - Slide Image Generation Prompt Template
  - Slide Quality Critique & Verification
  - Short-Form Video Clipping Editorial Brief
  - Gemini Direct Video Analysis Prompt
  - Transcript Context Summarization
  - Clip Candidate Critique & Boundary Repair
  - Speed Livestream Editor Brief
  - X Real-Time Research Prompt
  - X Post Drafting Prompt
  - Display Language & Romanization Rules

---

## Quick Start on Windows

### Hardware & Software Prerequisites

| Component | Recommended (This Environment) | Minimum / CPU-Only |
|---|---|---|
| **OS** | Windows 11 / 10 (64-bit) | Windows, Linux (Ubuntu 22.04+), macOS |
| **Python** | Python 3.11 – 3.13 (Installed in `.venv`) | Python 3.11+ |
| **Node.js** | Node.js 22 LTS or 24 LTS | Node.js 20+ (Required for yt-dlp & Web Studio) |
| **GPU** | NVIDIA RTX 4060 (8 GB VRAM) | Any NVIDIA GPU with 4GB+ VRAM, or CPU |
| **FFmpeg** | FFmpeg with `h264_nvenc`, `libass`, `loudnorm` | System FFmpeg or bundled imageio-ffmpeg |
| **Storage** | 10 GB+ free disk space | 3 GB free disk space |

### Option A: Launch Web Studio (1-Click)

Double-click `studio.bat` in the project root, or run in PowerShell:

```powershell
.\scripts\start-web.ps1
```

1. The terminal will start the FastAPI backend and serve the compiled React frontend at `http://127.0.0.1:8788`.
2. Your default browser will open automatically with your local authenticated launch key.
3. Access from any device on your Wi-Fi by visiting `http://<YOUR-PC-IP>:8788/#key=...`.

### Option B: Launch Private Telegram Bot

1. Open `.env` and paste your Telegram Bot Token from [@BotFather](https://t.me/BotFather):
   ```dotenv
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```
2. Start the bot:
   ```powershell
   .\scripts\start.ps1
   ```
3. Open Telegram, find your bot, and send `/whoami`.
4. Copy your numeric user ID, paste it into `ALLOWED_USER_IDS` in `.env`:
   ```dotenv
   ALLOWED_USER_IDS=987654321
   ```
5. Restart `scripts/start.ps1`. Send `/start` to access the full interactive dashboard!

### Option C: Render a Local Demo (No Credentials Needed)

Test the rendering engine, Whisper model, and NVENC encoder with synthetic speech and studio graphics:

```powershell
.\scripts\demo.ps1
```

This generates a full 1080×1920 video at `data/demo/<run>/` with real Whisper timestamps, custom fonts, and audio normalization.

### System Health Check (`cliper doctor`)

Verify your environment, FFmpeg filters, CUDA libraries, and AI configuration without contacting external services:

```powershell
.\.venv\Scripts\python.exe -m cliper doctor
```

Add `--online` to verify API keys and Telegram credentials:

```powershell
.\.venv\Scripts\python.exe -m cliper doctor --online
```

---

## Web Studio Guide

Open **CLIPER Studio** at `http://127.0.0.1:8788` (or double-click `studio.bat`).

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  cliper.  │  Studio  │  Speed Studio  │  X Studio  │  Carousels  │  Publishing  │ ⚙   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [ + New Project ]   [ Search (Ctrl+K) ]            Engine: [ Active ]  GPU: [ RTX 4060]│
│                                                                                        │
│  PROJECT WORKSPACE: "Joe Rogan Podcast #2100"                                         │
│  ┌───────────────────────┬──────────────────────────────────────────────────────────┐  │
│  │ SHORTLIST (5 Moments) │  VIDEO PREVIEW (1080x1920 @ 60fps)                       │  │
│  │ --------------------- │  ┌────────────────────────────────────────────────────┐  │  │
│  │ [✓] 01. AI Singularity│  │  WHITE HOOK TITLE PLACED ABOVE SQUARE VIDEO        │  │  │
│  │     04:12 - 04:58 (92)│  │  ┌──────────────────────────────────────────────┐ │  │  │
│  │                       │  │  │                                              │ │  │  │
│  │ [✓] 02. Quantum Leap  │  │  │           1080x1080 SQUARE VIDEO             │ │  │  │
│  │     12:30 - 13:15 (88)│  │  │           (YuNet Face-Tracked)               │ │  │  │
│  │                       │  │  │                                              │ │  │  │
│  │ [✓] 03. Brain Computer│  │  └──────────────────────────────────────────────┘ │  │  │
│  │     25:10 - 25:55 (85)│  │       MINT/YELLOW WORD-HIGHLIGHTED SUBTITLES      │  │  │
│  │                       │  └────────────────────────────────────────────────────┘  │  │
│  │ [Schedule All (3)]    │  [ Live Trim ]  [ Hook Editor ]  [ Subtitle Style ]       │  │
│  │ [Render Selected]     │  [ Music: Phonk (20%) ]  [ Publish to YouTube Shorts ]   │  │
│  └───────────────────────┴──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Project Dashboard & Intake

- Click **New Project** or press **N**.
- Paste a URL (YouTube, Twitch VOD, Kick, etc.) or drag-and-drop a local video file.
- Configure:
  - **AI Provider**: ChatGPT Browser, Gemini Web, OpenAI, xAI Grok, Gemini API, or Heuristic.
  - **Clipping Route**: Gemini Browser (direct link analysis) vs. Audio-First (Whisper scanner).
  - **Discovery Budget**: 6 to 1440 minutes.
  - **Focus Timestamps**: Prioritize specific moments (e.g., `00:15:30 01:45:00`).
  - **Requested Clips & Duration**: e.g., 5 clips between 30 and 60 seconds.

### Interactive Clip Editor

- **Video Stage**: Live preview of rendered MP4s with playback controls.
- **Waveform & Trimmer**: Fine-tune clip start and end timestamps down to 100 ms precision.
- **Grounded Hook Editor**: Edit the title that appears above the video. Choose between curiosity, contrast, or direct hook styles.
- **Caption & Subtitle Panel**: Modify transcript text and regenerate ASS/SRT cues.
- **Music Selector**: Assign a specific category (`Phonk`, `Chill - Ambient`, `Cinematic - Epic`) or select a specific track from the library.
- **Direct Publish Button**: Click "Publish" on any rendered clip to push directly to YouTube Shorts or Instagram Reels.

### Batch "Schedule All" to YouTube with Live-Clip Skipping

In the project view, click the **Schedule all** button:

1. **Target Platform**: Select **YouTube**.
2. **Channel Account**: Choose your authorized YouTube account (e.g. `main` or `gaming`).
3. **Posting Interval**: Choose the gap between releases (default: **2 hours**; supports any value from 0.5 to 72 hours).
4. **Publish First Now**: Toggle whether clip #1 goes live immediately or starts after the interval.
5. **Direct YouTube Scheduling**: When enabled, CLIPER uploads all clips directly to YouTube with `privacyStatus: private` and calculated `publishAt` timestamps.
6. **Smart Live-Clip Filter**: The modal displays how many clips are eligible and automatically excludes clips already marked `published` on YouTube.

### Mobile & Tablet Access over Local Network

CLIPER Web Studio binds to `0.0.0.0` by default. To control your studio from your phone or tablet:
1. Find your computer's local IP address (e.g., `192.168.1.50`).
2. Copy the full launch URL with your key from `data/web/access-key`:
   ```text
   http://192.168.1.50:8788/#key=YOUR_ACCESS_KEY
   ```
3. Open the URL in Safari, Chrome, or any mobile browser. You get full control over video generation, review, and scheduling from your phone!

### Studio Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + K` / `Cmd + K` | Open global project search and navigation palette |
| `N` | Open "New Project" modal |
| `?` | Show keyboard shortcuts and documentation help |
| `Escape` | Close any open modal or drawer |

---

## Publishing & Distribution Hub

### YouTube Data API v3 Multi-Account Setup

1. **Create Google Cloud Credentials**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project and enable the **YouTube Data API v3**.
   - Navigate to **APIs & Services > Credentials** and create an **OAuth 2.0 Client ID** (Application type: **Web application**).
   - Add Authorized redirect URIs:
     ```text
     http://127.0.0.1:8788/api/youtube/callback
     http://localhost:8788/api/youtube/callback
     ```
2. **Save Client ID & Secret**:
   - In Web Studio, open **Settings > Connections > YouTube**.
   - Enter your **Client ID** and **Client Secret**, then click **Save Google OAuth Credentials**.
   - Alternatively, add them to `.env`:
     ```dotenv
     YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
     YOUTUBE_CLIENT_SECRET=your-client-secret
     ```
3. **Authorize Channels**:
   - In Web Studio, click **+ Add YouTube Account**. Enter an account key (e.g., `main`, `gaming`, `shorts`).
   - Click **Authorize Channel**. A Google sign-in window will open. Grant permission and the channel will immediately show up as **Connected** with its title, avatar, and subscriber count.
   - Or authorize via PowerShell CLI:
     ```powershell
     .\scripts\youtube-auth.ps1 -Account main
     ```

### Native YouTube Scheduled Uploads (`publishAt`)

When scheduling a clip on YouTube, CLIPER leverages YouTube's native server-side scheduler:
- The video file is uploaded immediately via resumable chunked upload (4 MiB chunks).
- The video's `privacyStatus` is set to `private`.
- The `publishAt` parameter is set to the target UTC timestamp formatted in RFC 3339 (e.g., `2026-10-26T18:00:00.000Z`).
- YouTube's servers handle the public release automatically. Your local computer does not need to stay on at the moment of publication!

### Instagram Graph API Setup (Reels & Carousels)

1. Open `config/instagram.json`. Define your accounts:
   ```json
   {
     "clips": {
       "ig_user_id": "17841400000000000",
       "token_env": "IG_CLIPS_TOKEN",
       "login": "instagram",
       "owners": [123456789]
     }
   }
   ```
2. Put the matching access token in `.env`:
   ```dotenv
   IG_CLIPS_TOKEN=EAA...
   ```
3. Configure `PUBLIC_MEDIA_BASE_URL` to point to your HTTPS reverse proxy serving staged assets.

### Public Media Staging Server

Instagram requires public HTTPS URLs to fetch video and carousel images. Run the lightweight media server:

```powershell
.\.venv\Scripts\python.exe -m cliper serve-media --host 127.0.0.1 --port 8787
```

Forward your HTTPS reverse proxy (e.g. Nginx, Cloudflare Tunnel, Caddy) to `127.0.0.1:8787`.

### Publishing Queue Lifecycle

- **Review Inbox ("Needs Your Eye")**: Shows items requiring manual approval. Click to view media, edit captions, and approve or reject.
- **Scheduled Queue ("Up Next")**: Displays scheduled posts with countdowns and predecessor dependencies.
- **Published History ("Out in the World")**: Complete log of published assets. YouTube Shorts include a clickable link: `https://www.youtube.com/shorts/<video_id>`.
- **Uncertain State Guard**: If a network timeout occurs while waiting for confirmation from YouTube or Meta, the post is flagged as `uncertain`. CLIPER blocks automatic retries to prevent embarrassing duplicate posts.

---

## AI Providers & Selection Engines

CLIPER supports hot-swapping between zero-cost website automation and official high-throughput APIs.

```text
┌───────────────────────┬─────────────────────────┬─────────────────────────┬─────────────────────┐
│ AI Provider           │ Configuration           │ Setup Command           │ Cost / Limits       │
├───────────────────────┼─────────────────────────┼─────────────────────────┼─────────────────────┤
│ chatgpt_browser       │ Browser automation      │ .\scripts\chatgpt-login.ps1│ Free (ChatGPT Web)  │
│ gemini_browser        │ Browser automation      │ .\scripts\gemini-login.ps1 │ Free (Gemini Web)   │
│ openai                │ OPENAI_API_KEY          │ In .env or Web Studio   │ Paid API (Pay-as-go)│
│ xai (grok)            │ XAI_API_KEY             │ In .env or Web Studio   │ Paid API (Pay-as-go)│
│ gemini (api)          │ GEMINI_API_KEY          │ In .env or Web Studio   │ Paid API (Pay-as-go)│
│ heuristic             │ Fully offline           │ None required           │ 100% Free / Local   │
└───────────────────────┴─────────────────────────┴─────────────────────────┴─────────────────────┘
```

### Zero-Cost Website Adapters (ChatGPT & Gemini)

- **ChatGPT Login**:
  ```powershell
  .\scripts\chatgpt-login.ps1
  ```
  A Chromium window opens using `data/browsers/chatgpt-profile`. Sign in to your account, wait for the chat screen, and close the window.
- **Gemini Login**:
  ```powershell
  .\scripts\gemini-login.ps1
  ```
  Shares the same Chromium profile. Sign in once to enable Gemini browser clipping and carousel image rendering.
- **Headless Mode**:
  After verifying login, enable headless mode in `.env`:
  ```dotenv
  CHATGPT_BROWSER_HEADLESS=true
  ```

### Official API Providers (OpenAI, xAI Grok, Gemini API)

Configure your keys in `.env`:

```dotenv
AI_PROVIDER=xai

# xAI Grok
XAI_API_KEY=xai-your-api-key
XAI_MODEL=grok-4.6

# Google Gemini API
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4.1-mini
```

### Offline Heuristic Engine

When no internet connection or AI provider is available, select `heuristic`:
- Uses local speech volume, punctuation, and keyword cadence to rank candidate clips.
- Runs 100% locally with zero external API calls.

### Dynamic Provider Hot-Switching

Switch AI models at any time without restarting:
- **In Telegram**: `/provider grok`, `/provider gemini`, `/provider openai`, `/provider chatgpt`, `/provider heuristic`.
- **In Web Studio**: Open **Settings > AI & discovery** and select the provider from the dropdown.

---

## Editing Pipeline & Video Engineering

### Layouts: Square Hook vs. Full Vertical

1. **`square_hook` (Default & Recommended)**:
   - Centers a **1080×1080 square video** on a **1080×1920 black canvas** (9:16).
   - Places a **high-contrast bold white hook title** directly above the video frame.
   - Displays animated subtitles within the lower third, staying clear of platform UI buttons.
2. **`vertical_full`**:
   - Crops source footage to full 9:16 vertical resolution (1080×1920).
   - Ideal for single-subject vertical recordings or vlogs.

### Smart Face Tracking (OpenCV YuNet)

- Employs the lightweight OpenCV YuNet neural network to detect faces at 2 fps.
- **Deadband Smoothing**: Minor speaker head movements do not cause jittery pan movements.
- **Dropout Hold**: If a face turns away briefly, the crop position holds steady.
- **Scene-Cut Reset**: Instant recentering when camera angles change.
- **Wide-Group Preservation**: Keeps multiple speakers framed together for podcast and interview setups.

### Whisper Word Timestamps & Subtitle Typography

- Subtitles are driven by word-level timestamps generated by `faster-whisper`.
- Words are grouped into short, readable phrases (1–4 words).
- **Three Styling Themes**:
  - `studio`: Dark translucent pill background with mint cyan active-word highlight.
  - `bold`: High-visibility yellow active-word highlight with black outline.
  - `minimal`: Clean, unobtrusive white typography with drop shadow.

### Language Modes & Romanization (Hinglish)

In Web Studio Settings under **Hook & caption language**, choose:
- **Romanized (Default)**: Keeps original spoken audio, but transliterates captions, titles, and hashtags into the Latin alphabet (e.g. Hindi `तुम कैसे हो` → `tum kaise ho`).
- **English Translation**: Translates spoken dialogue into English phrases using your configured AI model.
- **Original Script**: Preserves native Devanagari, Arabic, or Cyrillic characters.

### Color Grading & HDR-to-SDR Tone Mapping

- **Natural**: Enhances contrast and adds subtle sharpness.
- **Vivid**: Saturated, vibrant colors suited for gaming and lifestyle content.
- **HDR Tone Mapping**: Automatically converts HDR10 (PQ) and HLG video into BT.709 SDR before grading, preventing washed-out colors.

### Hardware Acceleration (NVIDIA NVENC & CUDA)

Configured out-of-the-box for NVIDIA RTX GPUs:
```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=int8_float16
GPU_DEVICE_INDEX=0
VIDEO_ENCODER=h264_nvenc
```
For CPU-only computers, set `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, and `VIDEO_ENCODER=libx264`.

### Dual Export Architecture (Master vs. Telegram Compact)

- **High-Quality Master**: Rendered at up to 16 Mbps for pristine video fidelity. Used for Web Studio downloads, YouTube Shorts, and Instagram publishing.
- **Telegram Compact Delivery**: If the master exceeds Telegram's cloud file size limit, a second optimized copy is produced automatically for fast delivery to your phone.

---

## Music Library & Audio Processing

### The 64-Track Royalty-Free Catalog

CLIPER includes 64 curated, royalty-free tracks located in `music/`:

| Mood Category | Folder Path | Track Count | Style & Feel |
|---|---|---|---|
| **Energetic - Hype** | `music/Energetic - Hype` | 22 | Drift Phonk, Brazilian Phonk, Memphis Phonk, Sigma anthems, High-BPM EDM, Banjo swing |
| **Chill - Ambient** | `music/Chill - Ambient` | 12 | Lo-Fi Jazz Lounge, Acoustic Pop, Elevator meme, chill vlog |
| **Cinematic - Epic** | `music/Cinematic - Epic` | 9 | Orchestral builds, dramatic percussion, movie trailer climax |
| **Emotional - Sad** | `music/Emotional - Sad` | 8 | Melancholic piano, gentle strings, reflective moments |
| **Suspense - Thriller**| `music/Suspense - Thriller` | 7 | Dark ambient drones, rising tension, mystery cues |
| **Phonk** | `music/Phonk` | 6 | Aggressive 808 bass, distorted cowbells, gym motivation |

### Automated Speech Ducking & EBU R128 Loudness

- **Dynamic Speech Ducking**: Music volume is continuously monitored and attenuated whenever dialogue is detected, ensuring spoken words remain 100% intelligible.
- **EBU R128 Loudness Compliance**: The final mix passes through an FFmpeg `loudnorm` filter (`I=-16 LUFS, TP=-1.5 dBFS`) with a lookahead limiter to prevent clipping and distortion on smartphone speakers.

### Custom Track Uploads

- Drag-and-drop your own MP3, WAV, or AAC audio files into any category via Web Studio (**Music Library** tab).
- Preview tracks in the browser with interactive play/pause controls.

---

## CLI & Script Reference

### Command-Line Interface (`python -m cliper`)

```powershell
# Open Web Studio
python -m cliper web --port 8788 --open

# Start Telegram Bot & Worker
python -m cliper bot

# Check system prerequisites and encoders
python -m cliper doctor
python -m cliper doctor --online --provider gemini

# Process a local video file directly
python -m cliper run "C:\Videos\podcast.mp4" --clips 5 --min-seconds 30 --max-seconds 60

# Authenticate YouTube channel via OAuth
python -m cliper youtube-auth --account main
python -m cliper youtube-auth --list

# Browser logins
python -m cliper browser-login   # ChatGPT
python -m cliper gemini-login    # Google Gemini
python -m cliper x-login         # X (Twitter)

# Run synthetic demo render
python -m cliper demo --width 1080

# Clean up expired jobs
python -m cliper cleanup
```

### Automation PowerShell Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `studio.bat` | Double-click to launch Web Studio and open browser |
| `start.ps1` | Start the Telegram bot daemon |
| `start-web.ps1` | Start FastAPI backend and Vite frontend |
| `setup-gpu.ps1` | Install CUDA 12, cuDNN 9, and PyTorch GPU packages |
| `setup-web.ps1` | Install frontend Node dependencies (`npm ci`) |
| `youtube-auth.ps1` | Interactive YouTube channel OAuth authorization |
| `chatgpt-login.ps1` | Open Chromium for manual ChatGPT login |
| `gemini-login.ps1` | Open Chromium for manual Gemini login |
| `x-login.ps1` | Open Chromium for manual X login |
| `demo.ps1` | Render sample test clip without credentials |
| `allow-firewall.ps1` | Open Windows Firewall port 8788 for mobile access |

---

## Telegram Bot Commands

| Command | Arguments | Action |
|---|---|---|
| `/start` | None | Open interactive studio dashboard and main menu |
| `/help` | None | Display command reference and operational tips |
| `/whoami` | None | View your numeric Telegram user ID (for allowlist) |
| `/clip` | `<URL>` | Queue a public video for processing |
| `/geminiclip` | `<URL>` | Queue a YouTube video via zero-cost Gemini browser |
| `/speedclip` | `<URL>` | Queue a YouTube video with IShowSpeed energy preset |
| `/xpost` | `<desk> <topic>` | Queue real-time news research and X draft generation |
| `/jobs` | None | List your last 10 jobs with status and progress |
| `/status` | `<JOB_ID>` | Check job stage or reopen a waiting shortlist |
| `/render` | `<JOB_ID> 1,3,5` | Render specific clips from the shortlist |
| `/render` | `<JOB_ID> all` | Render all clips from the shortlist |
| `/cancel` | `<JOB_ID>` | Abort a queued or currently executing job |
| `/retry` | `<JOB_ID>` | Resume a failed job from the last valid checkpoint |
| `/export` | `<JOB_ID>` | Download ZIP of transcripts, SRT, ASS, and metadata |
| `/provider` | `<name>` | Switch AI model (`grok`, `gemini`, `openai`, `chatgpt`, `heuristic`) |
| `/clips` | `<1-10>` | Set default number of clips to generate |
| `/length` | `<min>-<max>` | Set clip duration boundaries in seconds (e.g., `30-60`) |
| `/style` | `<name>` | Set subtitle style (`studio`, `bold`, `minimal`) |
| `/captions` | `on` / `off` | Toggle burned-in subtitles |
| `/reframe` | `auto` / `blur` / `center` | Set framing method |
| `/autopublish` | `on` / `off` | Toggle automated Instagram publication |
| `/scan` | `<minutes>` | Set long-source discovery budget (6–1440 min) |
| `/focus` | `HH:MM:SS ...` | Prioritize specific timestamps in long streams |
| `/cleanup` | None | Manually purge expired completed and failed jobs |

---

## Configuration Reference (`.env` & `config/`)

### Key Environment Variables (`.env`)

```dotenv
# ==============================================================================
# TELEGRAM & SECURITY
# ==============================================================================
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ALLOWED_USER_IDS=123456789

# ==============================================================================
# AI PROVIDER SELECTION
# ==============================================================================
AI_PROVIDER=chatgpt_browser    # chatgpt_browser, gemini, xai, openai, heuristic
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
XAI_API_KEY=
XAI_MODEL=grok-4.6
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

# ==============================================================================
# BROWSER AUTOMATION (Playwright)
# ==============================================================================
CHATGPT_BROWSER_HEADLESS=false
CHATGPT_BROWSER_TIMEOUT=240
CHATGPT_BROWSER_MAX_CHARS=60000

# ==============================================================================
# YOUTUBE PUBLISHING (Data API v3)
# ==============================================================================
YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your-client-secret

# ==============================================================================
# INSTAGRAM GRAPH API
# ==============================================================================
IG_CLIPS_TOKEN=
IG_DARK_TOKEN=
PUBLIC_MEDIA_BASE_URL=https://media.yourdomain.com/cliper

# ==============================================================================
# GPU & HARDWARE ACCELERATION
# ==============================================================================
WHISPER_MODEL=small            # tiny, base, small, medium, large-v3
WHISPER_DEVICE=cuda            # cuda or cpu
WHISPER_COMPUTE_TYPE=int8_float16
GPU_DEVICE_INDEX=0
VIDEO_ENCODER=h264_nvenc       # h264_nvenc or libx264
```

### Configuration Files (`config/`)

- `config/youtube.json`: Multi-account YouTube channel configuration, tokens, default privacy, and tags.
- `config/instagram.json`: Multi-account Instagram account mappings, user IDs, and login types.
- `config/niches.json`: Content pillars, banned topics, and character reference paths for 5 carousel niches.
- `config/prompts.json`: User-customized prompt overrides for all clipping and scripting tasks.

---

## Troubleshooting & FAQ

### 1. "Permission denied" or User Allowlist Error on Telegram
- Send `/whoami` to your bot.
- Copy the numeric ID into `ALLOWED_USER_IDS` in `.env`.
- Restart `scripts/start.ps1`.

### 2. "CUDA error: out of memory" or Missing CUDA DLLs
- Run `.\scripts\setup-gpu.ps1` to ensure NVIDIA cuBLAS 12 and cuDNN 9 wheels are installed inside `.venv`.
- Run `python -m cliper doctor` to verify CUDA compute availability.
- If running out of VRAM, switch `WHISPER_MODEL=base` or `WHISPER_COMPUTE_TYPE=int8` in `.env`.

### 3. YouTube Upload Fails with "Invalid Credentials" or Token Expired
- Run `.\scripts\youtube-auth.ps1 -Account <key>` to re-authenticate the channel.
- Ensure your Google Cloud OAuth Consent Screen is published or your Google account is added as a Test User.

### 4. YouTube Upload Reaches Quota Limit
- The YouTube Data API provides a default free quota of 10,000 units per day.
- A video upload costs 1,600 units (approx. 6 uploads per day per Google Cloud project).
- To publish more clips, apply for a free quota extension in Google Cloud Console or add multiple OAuth client IDs.

### 5. Playwright Browser Login Window Does Not Appear
- Ensure `CHATGPT_BROWSER_HEADLESS=false` in `.env` before running `scripts/chatgpt-login.ps1` or `scripts/gemini-login.ps1`.

### 6. Subtitles Display Question Marks or Missing Font Glyphs
- The default subtitle engine uses Arial/DejaVu.
- For non-Latin scripts, set **Hook & caption language** to **Romanized** in Settings to convert text to clean Latin letters (e.g. Hindi → Hinglish).

---

## Repository Map

```text
cliper/
├── cliper/                       # Core Python backend engine
│   ├── bot.py                    # Telegram bot polling and inline UI
│   ├── browser_provider.py       # ChatGPT Web Playwright adapter
│   ├── captions.py               # ASS & SRT subtitle generator
│   ├── carousel.py               # Faceless 5-niche carousel generator
│   ├── cli.py                    # Command-line interface definitions
│   ├── config.py                 # Configuration loader and validation
│   ├── creative.py               # Carousel storytelling prompts & logic
│   ├── gemini_clipping.py        # Gemini Web zero-cost YouTube clipper
│   ├── gemini_images.py          # Gemini Web image generation adapter
│   ├── media.py                  # FFmpeg render pipeline, YuNet & NVENC
│   ├── models.py                 # Pydantic data schemas
│   ├── music.py                  # Background music catalog resolver
│   ├── pipeline.py               # Media intake & execution orchestrator
│   ├── prompts.py                # Unified AI Prompt Registry
│   ├── publishing.py             # Instagram Graph API publisher
│   ├── speed_edit.py             # IShowSpeed SFX & reaction zoom engine
│   ├── speed_profile.py          # IShowSpeed editorial brief & scoring
│   ├── storage.py                # SQLite database management
│   ├── stream_scan.py            # Long-stream bounded audio/caption scanner
│   ├── transcribe.py             # faster-whisper isolated worker
│   ├── vision.py                 # OpenCV YuNet face detection & tracking
│   ├── web.py                    # FastAPI REST API & WebSocket server
│   ├── x_browser.py              # X Web composer & publisher
│   ├── x_content.py              # X news research & fact verification
│   ├── x_studio.py               # X Studio state machine & scheduler
│   └── youtube_publishing.py     # YouTube Data API v3 publisher & OAuth
├── frontend/                     # Modern React 19 + Vite Web Studio
│   ├── src/
│   │   ├── App.tsx               # Studio shell, navigation, modals
│   │   ├── Project.tsx           # Clip editor, live stage, Schedule All
│   │   ├── Settings.tsx          # 6-tab deep configuration studio
│   │   ├── Speed.tsx             # IShowSpeed dedicated web workflow
│   │   ├── XStudio.tsx           # X news research & posting studio
│   │   ├── Workspaces.tsx        # Publishing, Carousels, Music Library
│   │   ├── styles.css            # Dark-mode design system & animations
│   │   └── types.ts              # TypeScript interfaces
├── config/                       # Configuration templates & account stores
│   ├── instagram.json            # Instagram account profiles
│   ├── niches.json               # Carousel niche brand definitions
│   ├── prompts.json              # Custom AI prompt overrides
│   └── youtube.json              # YouTube OAuth credentials & channels
├── music/                        # Curated 64-track royalty-free audio
│   ├── Chill - Ambient/          # Lofi, acoustic, vlog tracks
│   ├── Cinematic - Epic/         # Orchestral & dramatic scores
│   ├── Emotional - Sad/          # Melancholic piano & strings
│   ├── Energetic - Hype/         # Phonk, EDM, workout & dance
│   ├── Phonk/                    # Drift & Brazilian phonk
│   └── Suspense - Thriller/      # Dark drones & rising tension
├── scripts/                      # PowerShell & Python automation scripts
│   ├── start-web.ps1             # Launch Web Studio
│   ├── start.ps1                 # Launch Telegram bot
│   ├── youtube-auth.ps1          # Authorize YouTube channels
│   ├── chatgpt-login.ps1         # ChatGPT browser session setup
│   ├── gemini-login.ps1          # Gemini browser session setup
│   ├── x-login.ps1               # X browser session setup
│   └── setup-gpu.ps1             # NVIDIA CUDA & cuDNN setup
├── studio.bat                    # 1-Click Windows launcher for Web Studio
├── Dockerfile                    # Container definition
├── compose.yaml                  # Docker Compose deployment
└── pyproject.toml                # Python package metadata & dependencies
```

---

<p align="center">
  <b>Built for creators who value craftsmanship, automation, and privacy.</b><br>
  CLIPER operates completely on your local machine and private servers.
</p>
