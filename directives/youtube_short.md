# Directive: YouTube Fact-Bomb Short

## Goal
Produce a 30–60 second vertical (1080×1920) base video for a YouTube Short. The orchestrator (Claude) writes the script, the execution script assembles voiceover + stock footage into an MP4. Captions are added by the user in CapCut.

## Format rules (what makes a Short pop)
- **Hook in first 3 seconds.** Open with a curiosity gap or a "wait, what?" line.
- **45–60 seconds total** voiceover. Less than 30s underperforms; more than 60s drops retention.
- **One fact per video.** Don't list-dump.
- **Closer:** end with "Follow for more facts" or a teaser to the next video.
- **Voice:** clear, masculine, slightly dramatic. Default `en-US-GuyNeural` (Edge TTS). Alt: `en-US-AndrewNeural`.

## Inputs
A JSON script file at `clients/youtube/scripts/{slug}.json`:

```json
{
  "slug": "honey-never-spoils",
  "title": "Honey from Egyptian tombs is still edible 3,000 years later",
  "hook": "3,000-year-old honey was still edible",
  "voiceover": "...full narration text, one paragraph...",
  "emphasis": ["three thousand years old", "never spoils", "outlive you"],
  "shots": [
    {"query": "egyptian tomb", "duration": 4},
    {"query": "honey jar pouring", "duration": 4}
  ]
}
```

- `voiceover`: full narration. The execution script synthesizes this verbatim.
- `hook`: short title-card text (3–7 words) burned in for the first ~2 seconds, top of frame, yellow. Scroll-stopper.
- `emphasis`: phrases that get **yellow** highlighting in the captions. Pick 3–5 "shock words" per Short.
- `shots[].query`: Pexels search query. Pick visual, concrete nouns ("honey dripping" not "sweetness"). 4–7 shots per Short.
- `shots[].duration`: relative weight, not absolute seconds. The script normalizes to fit voiceover length.

## Tools
- `execution/generate_short.py` — main pipeline. Voiceover via ElevenLabs Adam if `ELEVENLABS_API_KEY` set (premium), else Edge TTS Guy (free fallback). Footage via Pexels API. Auto-burns styled captions (Anton font, white + yellow emphasis) and a hook card. Applies Ken Burns zoom to every clip.
- `.env` / GitHub secrets must contain `PEXELS_API_KEY` (required) and optionally `ELEVENLABS_API_KEY` (recommended for production voice).
- Pexels key: https://www.pexels.com/api/
- ElevenLabs key: https://elevenlabs.io → My Account → API Keys

## Run

### Cloud render (default — fully automated)
Any commit that adds or modifies `clients/youtube/scripts/*.json` triggers
`.github/workflows/render-short.yml`, which:
1. Installs ffmpeg + Python deps
2. Runs `execution/generate_short.py` for each changed script
3. Publishes the MP4 as a GitHub Release with a public download URL

You can also trigger a manual render from the Actions tab → "Render YouTube Short" → Run workflow → enter the slug (e.g. `honey-never-spoils`).

**One-time setup:** add `PEXELS_API_KEY` in repo Settings → Secrets and variables → Actions → New repository secret.

### Local render (fallback)
```
python execution/generate_short.py --script-file clients/youtube/scripts/honey-never-spoils.json
```

Output: `clients/youtube/{slug}/base.mp4` — drag into CapCut, hit auto-captions, export, upload.

## Outputs
- `clients/youtube/{slug}/base.mp4` — final base video
- `clients/youtube/{slug}/voice.mp3` — voiceover only (kept for re-edits)
- `clients/youtube/{slug}/clips/` — downloaded source clips

## Edge cases / learnings
- **No portrait results on Pexels:** the script falls back to landscape and center-crops to 9:16.
- **Clip shorter than allotted duration:** the script loops the clip to fill.
- **ElevenLabs upgrade path:** swap `edge_tts` for `elevenlabs` SDK if you want premium voice. Free Edge voices are good enough for ~95% of fact-bomb use.
- **Music:** not added by the script. Add in CapCut from the YouTube Audio Library — fact-bombs work best with low-key cinematic builds.
