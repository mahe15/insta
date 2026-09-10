import urllib.request
import urllib.parse
import os
import time
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Mahendra desai\OneDrive\Documentos\ChatGPT\cliper\music")

TRACKS = {
    "Chill - Ambient": [
        "Cattails.mp3",
        "Porch Swing Days - slower.mp3",
        "Porch Blues.mp3",
        "Clear Air.mp3"
    ],
    "Cinematic - Epic": [
        "Americana.mp3",
        "Pennsylvania Rose.mp3",
        "Neo Western.mp3"
    ],
    "Emotional - Sad": [
        "Just As Soon.mp3",
        "Long Road Ahead.mp3",
        "When The Wind Blows.mp3"
    ],
    "Energetic - Hype": [
        "Still Pickin.mp3",
        "Hillbilly Swing.mp3",
        "Bama Country.mp3",
        "River Valley Breakdown.mp3"
    ],
    "Suspense - Thriller": [
        "Southern Gothic.mp3",
        "Smoking Gun.mp3",
        "Western Streets.mp3",
        "Crowd Hammer.mp3"
    ]
}

def download_tracks():
    base_url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CliperMusicDownloader/1.0'}
    
    total = sum(len(v) for v in TRACKS.values())
    count = 0
    
    print(f"Starting download of {total} country/americana tracks into {BASE_DIR}...")
    
    for folder_name, files in TRACKS.items():
        folder_path = BASE_DIR / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing category: {folder_name}")
        for filename in files:
            count += 1
            dest = folder_path / filename
            if dest.exists() and dest.stat().st_size > 100_000:
                print(f"[{count}/{total}] Already exists: {filename} ({dest.stat().st_size:,} bytes)")
                continue
            
            url = base_url + urllib.parse.quote(filename)
            print(f"[{count}/{total}] Downloading: {filename} from {url}...")
            
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                    if len(data) < 100_000:
                        print(f"  WARNING: Downloaded file too small ({len(data)} bytes). Skipping.")
                        continue
                    with open(dest, "wb") as f:
                        f.write(data)
                    print(f"  Saved: {dest} ({len(data):,} bytes)")
            except Exception as e:
                print(f"  ERROR downloading {filename}: {e}")
            
            time.sleep(0.5)

    print("\nDownload complete!")

if __name__ == "__main__":
    download_tracks()
