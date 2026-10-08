"""
Download Comprehensive Music Catalog for CLIPER
Includes:
- Viral Phonk (Drift Phonk, Brazilian Phonk, GigaChad Phonk, Sigma Phonk, Tokyo Drift)
- Viral Hype & EDM (Monkeys Spinning Monkeys, Who Likes to Party, Future Gladiator, etc.)
- Viral Chill & Ambient (Carefree, Fluffing a Duck, Local Forecast, Lobby Time, etc.)
- Cinematic & Epic Orchestral (Hero Down, Crusade, Clash Defiant, Five Armies, etc.)
- Emotional & Melancholic Sad (Sad Trio, Heartbreaking, Grave Blow, Constance, etc.)
- Suspense & Mystery Thriller (Sneaky Snitch, Scheming Weasel, Investigations, Hitman, etc.)
"""

import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Mahendra desai\OneDrive\Documentos\ChatGPT\cliper\music")

TRACK_SOURCES = {
    "Energetic - Hype": [
        # --- VIRAL PHONK COLLECTION ---
        {
            "filename": "Kordhell - Murder In My Mind.mp3",
            "url": "https://archive.org/download/kordhell-murder-in-my-mind-extended/KORDHELL%20-%20MURDER%20IN%20MY%20MIND%20%5BExtended%5D.mp3",
            "artist": "Kordhell",
            "subgenre": "Drift Phonk / Aggressive Phonk",
            "mood": "Peak adrenaline, fast drift beats, heavy 808 bass",
        },
        {
            "filename": "DVRST - Close Eyes.mp3",
            "url": "https://archive.org/download/dvrst-close-eyes/DVRST%20-%20CLOSE%20EYES.mp3",
            "artist": "DVRST",
            "subgenre": "Drift Phonk / Viral TikTok Anthem",
            "mood": "Iconic Megamind glow-up beat, bouncy cowbell phonk",
        },
        {
            "filename": "Hensonn - Sahara.mp3",
            "url": "https://archive.org/download/hensonn-sahara-remix/HENSONN%20SAHARA%20REMIX.mp3",
            "artist": "Hensonn",
            "subgenre": "Drift Phonk / Dark Phonk",
            "mood": "Hypnotic driving rhythm, relentless speed, night drive",
        },
        {
            "filename": "Ghostface Playa - Why Not.mp3",
            "url": "https://archive.org/download/ghostface-playa-why-not/GHOSTFACE%20PLAYA%20-%20Why%20Not.mp3",
            "artist": "Ghostface Playa",
            "subgenre": "Memphis Phonk / Viral Walk Meme",
            "mood": "Dr. Livesey confident stride, massive 808 stomp",
        },
        {
            "filename": "Interworld - Metamorphosis.mp3",
            "url": "https://archive.org/download/interworld-metamorphosis/INTERWORLD%20-%20METAMORPHOSIS.mp3",
            "artist": "Interworld",
            "subgenre": "Drift Phonk / Electronic",
            "mood": "High velocity viral energy, intense synths",
        },
        {
            "filename": "g3ox_em - GigaChad Theme (Phonk House).mp3",
            "url": "https://archive.org/download/g-3ox-em-giga-chad-theme-phonk-house-version/g3ox_em%20-%20GigaChad%20Theme%20%28Phonk%20House%20Version%29.mp3",
            "artist": "g3ox_em",
            "subgenre": "Phonk House / Sigma Meme",
            "mood": "Ultimate confidence, heavy gym hype, viral Chad theme",
        },
        {
            "filename": "Orquestra Maldita - Brazilian Phonk.mp3",
            "url": "https://archive.org/download/orquestra-maldita-brazilian-phonk-320kbps/ORQUESTRA%20MALDITA%20%28BRAZILIAN%20PHONK%29_320kbps.mp3",
            "artist": "DJ Samir & DJ Shazam",
            "subgenre": "Brazilian Phonk / Favela Funk Beat",
            "mood": "Viral Reels Brazilian rhythm, energetic distortion, intense groove",
        },
        {
            "filename": "Interworld - Rapture.mp3",
            "url": "https://archive.org/download/interworld-rapture-phonk-i-5z-r-6to-pvq-8/INTERWORLD%20-%20RAPTURE%20%28PHONK%29_i5zR6toPVQ8.mp3",
            "artist": "Interworld",
            "subgenre": "Drift Phonk / Synthwave",
            "mood": "Fast pace, dark driving synthwave-phonk crossover",
        },
        {
            "filename": "Montagem - PR Funk.mp3",
            "url": "https://archive.org/download/montagem-pr-funk_202405/MONTAGEM%20-%20PR%20FUNK.mp3",
            "artist": "Montagem",
            "subgenre": "Brazilian Funk / Phonk",
            "mood": "Aggressive Brazilian phonk drops, TikTok dance beat",
        },
        {
            "filename": "Twisted - Worth Nothing.mp3",
            "url": "https://archive.org/download/worth-nothing-hanahata-remix/TWISTED%20-%20WORTH%20NOTHING%20%28hanahata%20remix%29%20-%2001%20-%20WORTH%20NOTHING%20%28hanahata%20remix%29.mp3",
            "artist": "Twisted (hanahata remix)",
            "subgenre": "Drift Phonk / Melodic Phonk",
            "mood": "Nostalgic melody overlaid with heavy distorted 808s",
        },
        {
            "filename": "Tokyo Drift - Phonk Edition.mp3",
            "url": "https://archive.org/download/phonk-antoshka-tokyo-drift-magic-free-release-1/Phonk%20%20Antoshka%20-%20Tokyo%20Drift%20%20%28Magic%20Free%20Release%29%20%281%29.mp3",
            "artist": "Antoshka",
            "subgenre": "Tokyo Drift Phonk",
            "mood": "Fast racing drift cowbell, high adrenaline street energy",
        },
        # --- VIRAL HYPE, EDM & ELECTRONIC ---
        {
            "filename": "Monkeys Spinning Monkeys.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Monkeys%20Spinning%20Monkeys.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Viral Meme / Upbeat Comedy",
            "mood": "The most viral TikTok background sound in history",
        },
        {
            "filename": "Who Likes to Party.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Who%20Likes%20to%20Party.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Dance / Electronic Hype",
            "mood": "Celebration, viral energy, party drop hype",
        },
        {
            "filename": "Future Gladiator.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Future%20Gladiator.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Electronic Rock / Gaming Hype",
            "mood": "Aggressive, high-speed action, gaming montage",
        },
        {
            "filename": "Raving Energy.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Raving%20Energy.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Fast Techno / Dance Hype",
            "mood": "Club rave pulse, high BPM, fitness & workout drive",
        },
        {
            "filename": "Movement Proposition.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Movement%20Proposition.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Action Synth Hype",
            "mood": "Fast electronic progression, relentless momentum",
        },
        {
            "filename": "The Complex.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Complex.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Cyber Electronic Drive",
            "mood": "Futuristic electronic beat, cyberpunk hype",
        },
        {
            "filename": "Volatile Reaction.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Action Hybrid Rock",
            "mood": "Adrenaline surge, sports & combat hype",
        },
    ],
    "Chill - Ambient": [
        {
            "filename": "Carefree.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Acoustic Pop / Happy Chill",
            "mood": "Warm, sunny, feel-good vlog & lifestyle classic",
        },
        {
            "filename": "Fluffing a Duck.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fluffing%20a%20Duck.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Comedic Chill / Cartoon Vibe",
            "mood": "Playful, lighthearted, silly viral explainer",
        },
        {
            "filename": "Local Forecast - Elevator.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Local%20Forecast%20-%20Elevator.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Muzak / Elevator Lounge Chill",
            "mood": "Iconic elevator waiting music, ironic chill vibe",
        },
        {
            "filename": "Lobby Time.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lobby%20Time.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Lo-Fi Jazz / Lounge Chill",
            "mood": "Relaxed jazz piano, easy-going hotel lounge aesthetic",
        },
        {
            "filename": "Airport Lounge.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Airport%20Lounge.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Bossa Nova / Lounge Chill",
            "mood": "Smooth, sophisticated, travel & lifestyle chill",
        },
        {
            "filename": "Mining by Moonlight.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mining%20by%20Moonlight.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Lo-Fi Study Piano",
            "mood": "Gentle, soothing midnight contemplation, study focus",
        },
        {
            "filename": "Danse Morialta.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Danse%20Morialta.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Acoustic Folk Chill",
            "mood": "Peaceful fingerstyle acoustic guitar lull",
        },
        {
            "filename": "Deliberate Thought.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Deliberate%20Thought.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Ambient Meditation",
            "mood": "Deep calming synthesizer pads, reflective thought",
        },
    ],
    "Cinematic - Epic": [
        {
            "filename": "Hero Down.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hero%20Down.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Trailer Orchestral",
            "mood": "Dramatic buildup from sacrifice to victorious triumph",
        },
        {
            "filename": "Prelude and Action.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Prelude%20and%20Action.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Action Orchestral",
            "mood": "Rapid string runs, thundering percussion, cinematic chase",
        },
        {
            "filename": "Crusade.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Crusade.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Choral / Battle Epic",
            "mood": "Grand historical conquest, mighty brass & choir power",
        },
        {
            "filename": "Clash Defiant.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clash%20Defiant.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "War Epic / Hybrid Trailer",
            "mood": "High stakes confrontation, battlefield intensity",
        },
        {
            "filename": "Five Armies.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Five%20Armies.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Fantasy Epic Climax",
            "mood": "Massive military clashes, soaring heroic horns",
        },
        {
            "filename": "Heroic Age.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heroic%20Age.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Majestic Fanfare",
            "mood": "Regal, noble, inspiring coronation & victory",
        },
        {
            "filename": "All This.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/All%20This.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Cinematic Drama",
            "mood": "Deep emotional weight, soaring cinematic swell",
        },
    ],
    "Emotional - Sad": [
        {
            "filename": "Sad Trio.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sad%20Trio.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Melancholic Chamber Strings",
            "mood": "Sorrowful cello, weeping violin, devastating sadness",
        },
        {
            "filename": "Heartbreaking.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Tragic Cinematic Strings",
            "mood": "Deep heartbreak, loss, tearjerker climax",
        },
        {
            "filename": "Grave Blow.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Grave%20Blow.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Dark Mournful Ambience",
            "mood": "Grief, despair, lonely dark atmospheric sorrow",
        },
        {
            "filename": "Constance.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Constance.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Bittersweet Sentimental Piano",
            "mood": "Gentle, nostalgic, touching memory of lost loved ones",
        },
        {
            "filename": "Mesmerize.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mesmerize.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Atmospheric Sadness",
            "mood": "Ethereal, haunting, quiet melancholy",
        },
    ],
    "Suspense - Thriller": [
        {
            "filename": "Scheming Weasel faster.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Scheming%20Weasel%20faster.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Viral Mischief / Plot Twist",
            "mood": "Sneaky conspiracy, dramatic reveal, mischievous suspense",
        },
        {
            "filename": "Sneaky Snitch.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Iconic Sneaky Comedy / Suspense",
            "mood": "The classic tiptoeing meme music, mystery & mischief",
        },
        {
            "filename": "Investigations.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Investigations.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Detective / Crime Suspense",
            "mood": "Solving the mystery, curious investigation, evidence reveal",
        },
        {
            "filename": "Hitman.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hitman.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Stealth Noir / Espionage",
            "mood": "Dark assassin in the shadows, tense tactical pulse",
        },
        {
            "filename": "Unseen Horrors.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Unseen%20Horrors.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Dark Psychological Horror",
            "mood": "Chilling dread, creeping terror, supernatural tension",
        },
        {
            "filename": "Right Behind You.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Right%20Behind%20You.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Stalker Thriller Pursuit",
            "mood": "Urgent danger, someone following in the shadows",
        },
        {
            "filename": "Static Motion.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Static%20Motion.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Cyber Mystery / Tech Suspense",
            "mood": "Cold electronic pulse, investigative intrigue",
        },
        {
            "filename": "Giant Wyrm.mp3",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Giant%20Wyrm.mp3",
            "artist": "Kevin MacLeod",
            "subgenre": "Monster / Ominous Tension",
            "mood": "Imposing dread, approaching monster, heavy suspense",
        },
    ],
}


def download_all():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CliperMusicSuite/2.0"}

    total = sum(len(tracks) for tracks in TRACK_SOURCES.values())
    current = 0
    success = 0
    skipped = 0
    failed = 0

    print(f"=== Starting Download of {total} Viral, Phonk & Background Music Tracks ===", flush=True)

    for category, tracks in TRACK_SOURCES.items():
        folder = BASE_DIR / category
        folder.mkdir(parents=True, exist_ok=True)
        print(f"\n[CATEGORY] [{category}] ({len(tracks)} tracks)", flush=True)

        for t in tracks:
            current += 1
            filename = t["filename"]
            url = t["url"]
            dest = folder / filename

            if dest.exists() and dest.stat().st_size > 150_000:
                print(f"  [{current}/{total}] [SKIP] Already present: {filename} ({dest.stat().st_size:,} bytes)", flush=True)
                skipped += 1
                continue

            print(f"  [{current}/{total}] [DOWNLOADING] {filename}...", flush=True)
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = resp.read()
                    if len(data) < 100_000:
                        print(f"    [WARN] File too small ({len(data)} bytes). Skipping.", flush=True)
                        failed += 1
                        continue
                    with open(dest, "wb") as f:
                        f.write(data)
                    print(f"    [OK] Saved ({len(data):,} bytes) - {t['subgenre']}", flush=True)
                    success += 1
            except Exception as e:
                print(f"    [ERROR] Downloading {filename}: {e}", flush=True)
                failed += 1

            time.sleep(0.3)

    print("\n" + "=" * 50, flush=True)
    print(f"Summary: Total={total} | Downloaded={success} | Existing={skipped} | Failed={failed}", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    download_all()
