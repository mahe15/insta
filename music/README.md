# Background music

Put music you have rights to use into these folders. Supported: MP3, WAV, M4A, AAC, FLAC, OGG.

- `Cinematic - Epic`: dramatic, powerful, motivational
- `Emotional - Sad`: emotional, touching, melancholic
- `Suspense - Thriller`: tension, mystery, curiosity
- `Energetic - Hype`: fast, exciting, high energy
- `Chill - Ambient`: calm, aesthetic, relaxing

The AI selects the category in JSON. CLIPER randomly chooses a track from that folder, saves the choice for retries, loops it as needed and mixes it at 0.20 gain under normalized speech. Empty folders leave speech unchanged and are reported in the clip metadata. No music is downloaded automatically.
