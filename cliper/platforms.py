"""Explicit public video/VOD destinations, backed by installed yt-dlp extractors."""
PLATFORMS = {
    "YouTube": ("youtube.com", "youtu.be"), "Twitch": ("twitch.tv",), "Kick": ("kick.com",),
    "Vimeo": ("vimeo.com",), "Facebook": ("facebook.com", "fb.watch"), "Instagram": ("instagram.com",),
    "TikTok": ("tiktok.com",), "X / Twitter": ("x.com", "twitter.com"),
    "Dailymotion": ("dailymotion.com", "dai.ly"), "Rumble": ("rumble.com",),
    "Bilibili": ("bilibili.com", "b23.tv"), "Odysee": ("odysee.com",),
}
DEFAULT_HOSTS = tuple(host for hosts in PLATFORMS.values() for host in hosts)


def help_text():
    return ("Normal clipping accepts public videos, saved broadcasts and clips from: " + ", ".join(PLATFORMS)
        + ".\nUse a specific VOD/clip URL for Kick or Twitch. Ongoing live channels, DRM and unavailable/private "
          "videos are not captured. Platform availability depends on yt-dlp and the host.\n"
          "Long VODs: captions first, then budgeted audio windows. /scan 24 sets a 24-minute scan budget; "
          "/focus 01:20:00 08:10:00 prioritizes known moments. Partial scans can miss highlights.")
