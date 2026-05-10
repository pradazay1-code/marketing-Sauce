#!/usr/bin/env python3
"""Generate a YouTube Short base video from a script JSON file.

Pipeline:
  1. Read script JSON (voiceover text + shot list).
  2. Synthesize voiceover with Edge TTS (free, no key).
  3. Search + download stock clips from Pexels (free key in .env).
  4. Crop each clip to 1080x1920 vertical and fit its allotted duration.
  5. Concatenate, attach voiceover, encode MP4.

Usage:
  python execution/generate_short.py --script-file clients/youtube/scripts/honey-never-spoils.json
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import edge_tts
import requests
from dotenv import load_dotenv
from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips

load_dotenv()

PEXELS_API = "https://api.pexels.com/videos/search"
DEFAULT_VOICE = "en-US-GuyNeural"
TARGET_W, TARGET_H = 1080, 1920
ROOT = Path(__file__).resolve().parent.parent


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _tts(text: str, out_path: Path, voice: str) -> None:
    await edge_tts.Communicate(text, voice).save(str(out_path))


def synthesize_voice(text: str, out_path: Path, voice: str) -> None:
    asyncio.run(_tts(text, out_path, voice))


def search_pexels_video(query: str, api_key: str) -> str | None:
    """Return a download URL for the best matching clip, or None."""
    headers = {"Authorization": api_key}
    for params in (
        {"query": query, "per_page": 5, "orientation": "portrait"},
        {"query": query, "per_page": 5},
    ):
        r = requests.get(PEXELS_API, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if videos:
            files = [f for f in videos[0]["video_files"] if (f.get("height") or 0) <= 1920]
            files = files or videos[0]["video_files"]
            files.sort(key=lambda f: -(f.get("height") or 0))
            return files[0]["link"]
    return None


def download(url: str, out_path: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


def to_vertical(clip):
    """Scale and center-crop a clip to 1080x1920."""
    src_ratio = clip.w / clip.h
    tgt_ratio = TARGET_W / TARGET_H
    if src_ratio > tgt_ratio:
        scaled = clip.resized(height=TARGET_H)
        x = scaled.w / 2
        return scaled.cropped(x1=x - TARGET_W / 2, x2=x + TARGET_W / 2)
    scaled = clip.resized(width=TARGET_W)
    y = scaled.h / 2
    return scaled.cropped(y1=y - TARGET_H / 2, y2=y + TARGET_H / 2)


def fit_duration(clip, target: float):
    """Trim or loop a clip to exactly `target` seconds."""
    if clip.duration >= target:
        return clip.subclipped(0, target)
    loops = int(target / clip.duration) + 1
    return concatenate_videoclips([clip] * loops, method="chain").subclipped(0, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a YouTube Short base video.")
    parser.add_argument("--script-file", required=True, help="Path to JSON script file")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Edge TTS voice name")
    args = parser.parse_args()

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        sys.exit("ERROR: PEXELS_API_KEY missing in .env (get one at https://www.pexels.com/api/)")

    script = json.loads(Path(args.script_file).read_text())
    slug = script.get("slug") or slugify(script["title"])
    out_dir = ROOT / "clients" / "youtube" / slug
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Synthesizing voiceover ({args.voice})...")
    voice_path = out_dir / "voice.mp3"
    synthesize_voice(script["voiceover"], voice_path, args.voice)
    voice_clip = AudioFileClip(str(voice_path))
    total = voice_clip.duration
    print(f"      {total:.1f}s")

    shots = script["shots"]
    weights = [s.get("duration", 1) for s in shots]
    durations = [(w / sum(weights)) * total for w in weights]

    print(f"[2/4] Fetching {len(shots)} stock clips from Pexels...")
    video_clips = []
    for i, (shot, dur) in enumerate(zip(shots, durations)):
        query = shot["query"]
        print(f"      [{i + 1}] '{query}' -> {dur:.1f}s")
        path = clips_dir / f"shot_{i:02d}.mp4"
        if not path.exists():
            url = search_pexels_video(query, api_key)
            if not url:
                print(f"      WARN: no Pexels results for '{query}', skipping")
                continue
            download(url, path)
        clip = VideoFileClip(str(path)).without_audio()
        clip = to_vertical(clip)
        clip = fit_duration(clip, dur)
        video_clips.append(clip)

    if not video_clips:
        sys.exit("ERROR: no clips downloaded; check queries or API key.")

    print("[3/4] Assembling...")
    video = concatenate_videoclips(video_clips, method="chain")
    video = video.with_audio(voice_clip).with_duration(total)

    out_path = out_dir / "base.mp4"
    print(f"[4/4] Encoding -> {out_path}")
    video.write_videofile(
        str(out_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )
    print(f"\nDone. Drop into CapCut, add captions, upload.\n  {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
