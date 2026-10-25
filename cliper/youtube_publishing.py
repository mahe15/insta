"""YouTube Data API v3 publishing and multi-account OAuth management."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .publishing import PublishStore

log = logging.getLogger("cliper.youtube")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _get_project_root(project_root: Path | str | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parent.parent


def get_youtube_config(project_root: Path | str | None = None) -> dict[str, Any]:
    root = _get_project_root(project_root)
    cfg_path = Path(os.getenv("YOUTUBE_ACCOUNTS_FILE", str(root / "config" / "youtube.json")))
    config: dict[str, Any] = {"client_id": "", "client_secret": "", "accounts": {}}
    if cfg_path.is_file():
        try:
            config = json.loads(cfg_path.read_text("utf-8"))
        except Exception as exc:
            log.warning("Could not read %s: %s", cfg_path, exc)

    if not isinstance(config.get("accounts"), dict):
        config["accounts"] = {}

    # Check client_secrets.json fallback if client_id or client_secret are not set
    if not config.get("client_id") or not config.get("client_secret"):
        client_secrets_path = root / "config" / "client_secrets.json"
        if not client_secrets_path.is_file():
            client_secrets_path = root / "client_secrets.json"
        if client_secrets_path.is_file():
            try:
                secret_data = json.loads(client_secrets_path.read_text("utf-8"))
                for section in ("installed", "web"):
                    if section in secret_data:
                        config["client_id"] = config.get("client_id") or secret_data[section].get("client_id", "")
                        config["client_secret"] = config.get("client_secret") or secret_data[section].get("client_secret", "")
                        break
            except Exception:
                pass

    # Check environment variable fallbacks
    config["client_id"] = config.get("client_id") or os.getenv("YOUTUBE_CLIENT_ID", "")
    config["client_secret"] = config.get("client_secret") or os.getenv("YOUTUBE_CLIENT_SECRET", "")

    # Discover any orphaned token files in data/youtube/tokens/
    data_dir = root / "data"
    tokens_dir = data_dir / "youtube" / "tokens"
    if tokens_dir.is_dir():
        for tf in tokens_dir.glob("*.json"):
            clean_stem = tf.stem.lower()
            if not any(k.lower() == clean_stem for k in config["accounts"]):
                config["accounts"][clean_stem] = {
                    "channel_id": "",
                    "title": tf.stem,
                    "privacy": "public",
                    "default_tags": ["shorts", "clips"],
                    "auto_publish": False,
                    "owners": [0],
                }
    return config


def save_youtube_config(data: dict[str, Any], project_root: Path | str | None = None) -> None:
    root = _get_project_root(project_root)
    cfg_path = Path(os.getenv("YOUTUBE_ACCOUNTS_FILE", str(root / "config" / "youtube.json")))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_token_path(account_key: str, data_dir: Path | str = "data") -> Path:
    clean_key = re.sub(r"[^\w-]", "_", account_key)
    tokens_dir = Path(data_dir) / "youtube" / "tokens"
    if tokens_dir.is_dir():
        for tf in tokens_dir.glob("*.json"):
            if tf.stem.lower() == clean_key.lower():
                return tf
    return tokens_dir / f"{clean_key}.json"


def get_credentials(account_key: str, data_dir: Path | str = "data", project_root: Path | str | None = None) -> Credentials:
    token_path = get_token_path(account_key, data_dir)
    if not token_path.is_file():
        raise ValueError(f"YouTube account '{account_key}' is not authorized. Please authorize it first.")

    try:
        token_info = json.loads(token_path.read_text("utf-8"))
    except Exception as exc:
        raise ValueError(f"Corrupted token for account '{account_key}': {exc}") from exc

    cfg = get_youtube_config(project_root)
    client_id = token_info.get("client_id") or cfg.get("client_id")
    client_secret = token_info.get("client_secret") or cfg.get("client_secret")

    creds = Credentials(
        token=token_info.get("token"),
        refresh_token=token_info.get("refresh_token"),
        token_uri=token_info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=client_id,
        client_secret=client_secret,
        scopes=token_info.get("scopes", YOUTUBE_SCOPES),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(account_key, creds, data_dir)
        except Exception as exc:
            raise ValueError(f"Failed to refresh YouTube token for '{account_key}': {exc}") from exc

    return creds


def save_credentials(account_key: str, creds: Credentials, data_dir: Path | str = "data") -> None:
    token_path = get_token_path(account_key, data_dir)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or YOUTUBE_SCOPES),
    }
    token_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def fetch_channel_profile(creds: Credentials) -> dict[str, Any]:
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise ValueError("No YouTube channel found for the authorized Google account.")
    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    thumbnails = snippet.get("thumbnails", {})
    thumb_url = (
        thumbnails.get("default", {}).get("url")
        or thumbnails.get("medium", {}).get("url")
        or ""
    )
    return {
        "channel_id": item.get("id", ""),
        "title": snippet.get("title", ""),
        "custom_url": snippet.get("customUrl", ""),
        "thumbnail": thumb_url,
        "subscriber_count": stats.get("subscriberCount", "0"),
        "video_count": stats.get("videoCount", "0"),
    }


def upload_to_youtube(
    account_key: str,
    video_path: str | Path,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str = "public",
    made_for_kids: bool = False,
    is_short: bool = True,
    publish_at: str | float | int | Any | None = None,
    project_root: Path | str | None = None,
    data_dir: Path | str = "data",
    progress_callback=None,
) -> dict[str, Any]:
    path = Path(video_path).resolve()
    if not path.is_file():
        raise ValueError(f"Video file not found: {video_path}")

    creds = get_credentials(account_key, data_dir=data_dir, project_root=project_root)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    tags = list(tags or [])
    # Guarantee #Shorts tag/hashtag is in title or description for vertical short-form distribution
    clean_title = (title or "New Clip").strip()
    if is_short and "#shorts" not in clean_title.lower():
        clean_title = (clean_title[:91] + " #Shorts").strip()
    else:
        clean_title = clean_title[:100]

    clean_desc = (description or "").strip()
    if is_short and "#shorts" not in clean_desc.lower():
        clean_desc = (clean_desc + "\n\n#Shorts #Viral #Clips").strip()
    clean_desc = clean_desc[:5000]

    if is_short and "shorts" not in [t.lower() for t in tags]:
        tags.append("shorts")

    if privacy not in {"public", "unlisted", "private"}:
        privacy = "public"

    from datetime import datetime, timezone
    publish_at_iso = None
    if publish_at is not None:
        target_ts: float | None = None
        if isinstance(publish_at, (int, float)):
            target_ts = float(publish_at)
        elif isinstance(publish_at, str) and publish_at.strip():
            s = publish_at.strip()
            try:
                target_ts = float(s)
            except ValueError:
                try:
                    dt_parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    target_ts = dt_parsed.timestamp()
                except Exception as exc:
                    log.warning("Could not parse publish_at string '%s': %s", s, exc)
        elif hasattr(publish_at, "timestamp"):
            target_ts = publish_at.timestamp()

        if target_ts is not None:
            now_ts = time.time()
            # YouTube API requires publishAt to be in the future (at least ~1 min ahead).
            # If target_ts is in the past or within 60s, clamp to 120s ahead so scheduling succeeds.
            if target_ts <= now_ts + 60:
                target_ts = now_ts + 120
            dt = datetime.fromtimestamp(target_ts, tz=timezone.utc)
            publish_at_iso = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    status_dict: dict[str, Any] = {
        "selfDeclaredMadeForKids": bool(made_for_kids),
    }
    if publish_at_iso:
        # YouTube Data API v3 requirement:
        # Scheduled publishing requires privacyStatus='private' and an RFC 3339 publishAt timestamp.
        status_dict["privacyStatus"] = "private"
        status_dict["publishAt"] = publish_at_iso
    else:
        status_dict["privacyStatus"] = privacy

    body = {
        "snippet": {
            "title": clean_title,
            "description": clean_desc,
            "tags": tags[:500],
            "categoryId": "22",  # People & Blogs
        },
        "status": status_dict,
    }

    media = MediaFileUpload(str(path), chunksize=4 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and progress_callback:
            try:
                progress_callback(int(status.progress() * 100))
            except Exception:
                pass

    video_id = response.get("id")
    if not video_id:
        raise ValueError("YouTube API did not return a video ID")

    resp_status = response.get("status", {})
    return {
        "id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "shorts_url": f"https://www.youtube.com/shorts/{video_id}",
        "status": "scheduled" if publish_at_iso else resp_status.get("privacyStatus", privacy),
        "scheduled_at": publish_at_iso,
    }


class YouTubePublisher:
    """Processes queued publications for YouTube destinations."""

    def __init__(self, store: PublishStore, cfg=None, project_root: Path | str | None = None):
        self.store = store
        self.cfg = cfg
        self.project_root = _get_project_root(project_root)
        self.data_dir = getattr(cfg, "data_dir", Path("data")) if cfg else Path("data")

    async def process(self, post: dict[str, Any]) -> str:
        account_key = post["account"]
        cfg_data = get_youtube_config(self.project_root)
        account_info = cfg_data.get("accounts", {}).get(account_key)
        if not account_info:
            raise ValueError(f"YouTube account '{account_key}' is not configured in config/youtube.json")

        owner = post.get("owner", 0)
        allowed_owners = set(account_info.get("owners", [0]))
        if owner not in allowed_owners and owner != 0 and 0 not in allowed_owners:
            raise ValueError(f"Telegram owner {owner} is not authorized for YouTube account '{account_key}'")

        payload = json.loads(post["payload"])
        paths = payload.get("paths", [])
        if not paths:
            raise ValueError("No video media path in publication payload")
        video_path = Path(paths[0])
        if not video_path.is_file() or video_path.suffix.lower() != ".mp4":
            raise ValueError(f"Publication asset is not an existing MP4 video: {video_path}")

        title = payload.get("title") or payload.get("caption", "").split("\n")[0][:90] or "Clip"
        description = payload.get("description") or payload.get("caption", "")
        tags = payload.get("tags") or account_info.get("default_tags", ["shorts", "clips"])
        privacy = payload.get("privacy") or account_info.get("privacy", "public")
        made_for_kids = payload.get("made_for_kids", False)

        channel_id = account_info.get("channel_id", "")
        self.store.update(post["id"], target_id=channel_id)

        # Pre-publish lock to avoid duplicate attempts
        self.store.update(post["id"], state="publishing")

        due = post.get("due")
        publish_at = due if (due and due > time.time() + 60) else None

        try:
            result = await asyncio.to_thread(
                upload_to_youtube,
                account_key=account_key,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                privacy=privacy,
                made_for_kids=made_for_kids,
                is_short=True,
                publish_at=publish_at,
                project_root=self.project_root,
                data_dir=self.data_dir,
            )
        except HttpError as exc:
            err_msg = f"YouTube API Error ({exc.status_code}): {exc.reason}"
            if "quotaExceeded" in str(exc):
                err_msg = "YouTube daily API upload quota exceeded. Try again tomorrow."
            self.store.update(post["id"], state="failed", error=err_msg)
            raise ValueError(err_msg) from exc
        except Exception as exc:
            self.store.update(post["id"], state="uncertain", error=f"Interrupted during YouTube publish: {exc}")
            raise

        video_id = result["id"]
        self.store.update(
            post["id"],
            state="published",
            media_id=video_id,
            published_at=time.time(),
            error="",
        )
        return video_id

    async def run(self, notify):
        self.store.recover(platform="youtube")
        while True:
            post = self.store.claim(platform="youtube")
            if not post:
                await asyncio.sleep(2)
                continue
            try:
                video_id = await self.process(post)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.store.get(post["id"])["state"] not in {"uncertain", "approval"}:
                    self.store.update(
                        post["id"],
                        state="failed",
                        error=str(exc)[:500] if isinstance(exc, ValueError) else "YouTube upload failed; inspect settings",
                    )
                message = f"YouTube {post['id']}: {self.store.get(post['id'])['error']}"
            else:
                message = f"Published to YouTube Shorts · {post['id']} · https://youtu.be/{video_id}"
            try:
                await notify(post, message)
            except Exception:
                pass


async def run_cli_auth(account_key: str, cfg=None):
    """Run local desktop OAuth flow to authorize a YouTube account."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    yt_cfg = get_youtube_config()
    client_id = yt_cfg.get("client_id")
    client_secret = yt_cfg.get("client_secret")
    if not client_id or not client_secret:
        print("\n[!] Error: Please configure client_id and client_secret in config/youtube.json or .env first.")
        print("    You can also enter them directly in Studio Settings under 'YouTube Channels'.")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=YOUTUBE_SCOPES)
    print(f"\n[+] Starting OAuth flow for YouTube account '{account_key}'...")
    print("    Your default browser will open to select your Google account / YouTube channel.")
    creds = await asyncio.to_thread(flow.run_local_server, port=8088, prompt="select_account consent")
    data_dir = getattr(cfg, "data_dir", Path("data")) if cfg else Path("data")
    save_credentials(account_key, creds, data_dir)

    try:
        profile = await asyncio.to_thread(fetch_channel_profile, creds)
        print(f"\n[✓] Success! Authorized YouTube channel: {profile.get('title')} ({profile.get('channel_id')})")
        accounts = yt_cfg.setdefault("accounts", {})
        accounts[account_key] = accounts.get(account_key, {}) | {
            "channel_id": profile.get("channel_id", ""),
            "title": profile.get("title", account_key),
            "thumbnail": profile.get("thumbnail", ""),
        }
        save_youtube_config(yt_cfg)
        print(f"    Account mapping saved to config/youtube.json")
    except Exception as exc:
        print(f"\n[!] Token saved for '{account_key}', but could not fetch channel metadata: {exc}")


def list_accounts_cli(project_root: Path | str | None = None) -> None:
    """Print configured YouTube accounts to stdout."""
    cfg = get_youtube_config(project_root)
    accounts = cfg.get("accounts", {})
    if not accounts:
        print("\nNo YouTube accounts configured yet in config/youtube.json.")
        return
    print("\nCurrently configured YouTube accounts:")
    for k, v in accounts.items():
        token_path = get_token_path(k)
        status = "Connected" if token_path.is_file() else "Needs Auth"
        title = v.get("title") or k
        cid = v.get("channel_id") or "No Channel ID"
        print(f"  • {k:12} : \"{title}\" (ID: {cid}) [{status}]")
    print()


def suggest_next_account_key(project_root: Path | str | None = None) -> str:
    """Suggest next available unique account key."""
    cfg = get_youtube_config(project_root)
    accounts = {k.lower() for k in cfg.get("accounts", {})}
    if "main" not in accounts:
        return "main"
    i = 2
    while f"channel_{i}" in accounts:
        i += 1
    return f"channel_{i}"


