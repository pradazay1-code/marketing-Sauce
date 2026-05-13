#!/usr/bin/env python3
"""Generate a long-form (10-30 min) documentary-style video.

Differences from generate_short.py:
  - 16:9 landscape (1920x1080) instead of 9:16 vertical
  - Multi-source footage: Pexels -> Pixabay -> Wikimedia -> Pollinations AI image gen
  - Edge TTS "AndrewMultilingualNeural" voice (free, conversational, holds long listen)
  - No burned-in captions
  - Optional background music looped under voice
  - Soft Ken Burns motion (gentler than Shorts pipeline)

Usage:
  python execution/generate_longform.py --script-file clients/youtube/longform-scripts/tesla-robotaxi.json
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import edge_tts
import requests
from dotenv import load_dotenv
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume
from moviepy.video.fx.Resize import Resize

load_dotenv()

PEXELS_API = "https://api.pexels.com/videos/search"
PIXABAY_VIDEO_API = "https://pixabay.com/api/videos/"
PIXABAY_IMAGE_API = "https://pixabay.com/api/"
WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
POLLINATIONS_IMG = "https://image.pollinations.ai/prompt/"

DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"
TARGET_W, TARGET_H = 1920, 1080
KEN_BURNS_ZOOM = 1.06
MUSIC_VOLUME = 0.10
ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "longform-renderer/1.0 (contact@aventis.marketing)"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ----- Voice synthesis (Edge TTS Multilingual) -----


async def _tts(text: str, out_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])


def synthesize_voice(text: str, out_path: Path, voice: str = DEFAULT_VOICE) -> None:
    asyncio.run(_tts(text, out_path, voice))


# ----- Source: Pexels Videos -----


def search_pexels(query: str, api_key: str):
    try:
        r = requests.get(
            PEXELS_API,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 3, "orientation": "landscape"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        videos = r.json().get("videos", [])
        if not videos:
            return None
        files = [f for f in videos[0]["video_files"] if (f.get("height") or 0) <= 1080]
        files = files or videos[0]["video_files"]
        files.sort(key=lambda f: -(f.get("height") or 0))
        return files[0]["link"]
    except Exception:
        return None


# ----- Source: Pixabay Videos + Images -----


def search_pixabay_video(query: str, api_key: str):
    if not api_key:
        return None
    try:
        r = requests.get(
            PIXABAY_VIDEO_API,
            params={"key": api_key, "q": query, "per_page": 3, "safesearch": "true"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        if not hits:
            return None
        # Prefer "medium" quality (smaller file, still HD)
        videos = hits[0].get("videos", {})
        for size in ("medium", "small", "large", "tiny"):
            if size in videos and videos[size].get("url"):
                return videos[size]["url"]
        return None
    except Exception:
        return None


def search_pixabay_image(query: str, api_key: str):
    if not api_key:
        return None
    try:
        r = requests.get(
            PIXABAY_IMAGE_API,
            params={"key": api_key, "q": query, "per_page": 3, "orientation": "horizontal", "safesearch": "true"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        if not hits:
            return None
        return hits[0].get("largeImageURL") or hits[0].get("webformatURL")
    except Exception:
        return None


# ----- Source: Wikimedia Commons -----


def search_wikimedia_image(query: str):
    """Search Wikimedia Commons for a relevant image (good for faces, public figures, branded products)."""
    try:
        r = requests.get(
            WIKIMEDIA_API,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query + " filetype:bitmap",
                "srnamespace": 6,
                "srlimit": 5,
            },
            timeout=20,
            headers=UA,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0]["title"]
        # Resolve file URL
        r2 = requests.get(
            WIKIMEDIA_API,
            params={
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 1920,
            },
            timeout=20,
            headers=UA,
        )
        pages = r2.json().get("query", {}).get("pages", {})
        for p in pages.values():
            ii = p.get("imageinfo", [])
            if ii:
                return ii[0].get("thumburl") or ii[0].get("url")
        return None
    except Exception:
        return None


# ----- Source: Pollinations AI image gen (free, no key) -----


def pollinations_image_url(prompt: str) -> str:
    return f"{POLLINATIONS_IMG}{quote(prompt)}?width=1920&height=1080&nologo=true&seed=42"


# ----- Download helper -----


def download(url: str, out_path: Path):
    with requests.get(url, stream=True, timeout=180, headers=UA) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    return out_path


# ----- Shot resolution: try sources in order -----


def fetch_shot(
    idx: int,
    query: str,
    duration: float,
    clips_dir: Path,
    pexels_key: str,
    pixabay_key: str | None,
    preferred_sources: list[str] | None = None,
):
    """Try multiple sources to fetch this shot. Returns (path, kind) where kind in {'video','image'}."""
    video_path = clips_dir / f"shot_{idx:04d}.mp4"
    image_path = clips_dir / f"shot_{idx:04d}.jpg"

    if video_path.exists():
        return video_path, "video"
    if image_path.exists():
        return image_path, "image"

    sources = preferred_sources or ["pexels", "pixabay", "wikimedia", "ai"]
    for src in sources:
        try:
            if src == "pexels":
                url = search_pexels(query, pexels_key)
                if url:
                    download(url, video_path)
                    return video_path, "video"
            elif src == "pixabay":
                url = search_pixabay_video(query, pixabay_key)
                if url:
                    download(url, video_path)
                    return video_path, "video"
            elif src == "pixabay_image":
                url = search_pixabay_image(query, pixabay_key)
                if url:
                    download(url, image_path)
                    return image_path, "image"
            elif src == "wikimedia":
                url = search_wikimedia_image(query)
                if url:
                    download(url, image_path)
                    return image_path, "image"
            elif src == "ai":
                url = pollinations_image_url(query)
                download(url, image_path)
                return image_path, "image"
        except Exception as e:
            print(f"      [{src}] failed for '{query}': {e}")
            continue

    return None, None


# ----- Clip processing -----


def fit_landscape(clip, target_duration: float, zoom_to: float = KEN_BURNS_ZOOM):
    # Trim/loop to target duration
    if clip.duration >= target_duration:
        clip = clip.subclipped(0, target_duration)
    else:
        loops = int(target_duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * loops, method="chain").subclipped(0, target_duration)

    # Resize + center-crop to 1920x1080
    src_ratio = clip.w / clip.h
    tgt_ratio = TARGET_W / TARGET_H
    if src_ratio > tgt_ratio:
        clip = clip.resized(height=TARGET_H)
        x = clip.w / 2
        clip = clip.cropped(x1=x - TARGET_W / 2, x2=x + TARGET_W / 2)
    else:
        clip = clip.resized(width=TARGET_W)
        y = clip.h / 2
        clip = clip.cropped(y1=y - TARGET_H / 2, y2=y + TARGET_H / 2)

    # Soft Ken Burns zoom
    d = clip.duration
    clip = clip.with_effects([Resize(lambda t, d=d: 1 + (zoom_to - 1) * t / d)])
    return clip


def load_clip(path: Path, kind: str, duration: float):
    if kind == "image":
        clip = ImageClip(str(path)).with_duration(duration)
    else:
        clip = VideoFileClip(str(path)).without_audio()
    return fit_landscape(clip, duration)


# ----- Music: loop / fit to total length -----


def prepare_music(music_path: Path, total_duration: float):
    music = AudioFileClip(str(music_path))
    if music.duration < total_duration:
        # Loop by concatenation
        from moviepy import concatenate_audioclips
        loops = int(total_duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops)
    music = music.subclipped(0, total_duration)
    music = music.with_effects([MultiplyVolume(MUSIC_VOLUME)])
    return music


# ----- Main -----


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script-file", required=True)
    args = parser.parse_args()

    pexels_key = os.getenv("PEXELS_API_KEY")
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    if not pexels_key:
        sys.exit("ERROR: PEXELS_API_KEY missing in .env / GitHub secrets")
    if not pixabay_key:
        print("WARN: PIXABAY_API_KEY not set — falling back to Pexels + Wikimedia + AI only")

    script = json.loads(Path(args.script_file).read_text())
    slug = script.get("slug") or slugify(script["title"])
    voice = script.get("voice", DEFAULT_VOICE)
    out_dir = ROOT / "clients" / "youtube" / "longform" / slug
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 1. Voice
    print(f"[1/4] Synthesizing voice ({voice})...")
    voice_path = out_dir / "voice.mp3"
    synthesize_voice(script["voiceover"], voice_path, voice)
    voice_clip = AudioFileClip(str(voice_path))
    total_duration = voice_clip.duration
    print(f"      voiceover: {total_duration:.1f}s ({total_duration/60:.1f} min)")

    # 2. Fit shot durations to voiceover length
    shots = script["shots"]
    weights = [s.get("duration", 1) for s in shots]
    weight_sum = sum(weights)
    durations = [(w / weight_sum) * total_duration for w in weights]

    print(f"[2/4] Fetching {len(shots)} shots from multi-source pool...")
    video_clips = []
    for i, (shot, dur) in enumerate(zip(shots, durations)):
        query = shot["query"]
        preferred = shot.get("sources")
        if (i + 1) % 25 == 0 or i == 0:
            print(f"      [{i+1}/{len(shots)}] '{query}' -> {dur:.1f}s")
        path, kind = fetch_shot(i, query, dur, clips_dir, pexels_key, pixabay_key, preferred)
        if not path:
            print(f"      [{i+1}] WARN no source matched '{query}'")
            continue
        try:
            clip = load_clip(path, kind, dur)
            video_clips.append(clip)
        except Exception as e:
            print(f"      [{i+1}] WARN clip load failed for '{query}': {e}")

    if not video_clips:
        sys.exit("ERROR: no usable clips")

    print(f"      {len(video_clips)} clips ready ({sum(c.duration for c in video_clips):.1f}s coverage)")

    # 3. Compose timeline
    print("[3/4] Compositing timeline + audio...")
    timeline = []
    t = 0.0
    for clip in video_clips:
        timeline.append(clip.with_start(t).with_position("center"))
        t += clip.duration

    video = CompositeVideoClip(timeline, size=(TARGET_W, TARGET_H)).with_duration(min(t, total_duration))

    # Audio: voice + optional music
    audio_tracks = [voice_clip]
    music_file = script.get("music_file")
    if music_file:
        music_path = ROOT / music_file
        if music_path.exists():
            print(f"      mixing music: {music_path.name}")
            music = prepare_music(music_path, total_duration)
            from moviepy import CompositeAudioClip
            audio_tracks.append(music)
        else:
            print(f"      WARN music file not found: {music_path}")

    if len(audio_tracks) > 1:
        from moviepy import CompositeAudioClip
        final_audio = CompositeAudioClip(audio_tracks)
    else:
        final_audio = voice_clip

    video = video.with_audio(final_audio).with_duration(total_duration)

    # 4. Encode
    out_path = out_dir / "video.mp4"
    print(f"[4/4] Encoding -> {out_path} ...")
    video.write_videofile(
        str(out_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        bitrate="6000k",
        logger=None,
    )
    print(f"\nDone -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
