#!/usr/bin/env python3
"""V2 long-form documentary pipeline.

Improvements over V1:
  - Brand asset library (curated URLs override generic search)
  - yt-dlp for real branded YouTube footage (trimmed to short snippets — fair use commentary)
  - Targeted Wikimedia Commons category search
  - Brian Multilingual voice (more conversational than Andrew)
  - Optional shot-to-script timestamp alignment via `at` field
  - 16:9 1920x1080, no captions, soft Ken Burns motion, background music

Source priority per shot (highest to lowest):
  1. Explicit `url` in script JSON
  2. Brand library match (clients/youtube/assets/brand-library.json)
  3. yt-dlp YouTube search (trimmed to 8-12s)
  4. Pexels Videos
  5. Pixabay Videos
  6. Wikimedia Commons
  7. Pollinations AI image gen

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
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
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

DEFAULT_VOICE = "en-US-BrianMultilingualNeural"
TARGET_W, TARGET_H = 1920, 1080
KEN_BURNS_ZOOM = 1.06
MUSIC_VOLUME = 0.10
YT_TRIM_SECONDS = 12
ROOT = Path(__file__).resolve().parent.parent
BRAND_LIBRARY = ROOT / "clients" / "youtube" / "assets" / "brand-library.json"
UA = {"User-Agent": "longform-renderer/2.0"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


# ----- Voice synthesis -----


async def _tts(text: str, out_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])


def synthesize_voice(text: str, out_path: Path, voice: str = DEFAULT_VOICE) -> None:
    asyncio.run(_tts(text, out_path, voice))


# ----- Source 1: Brand library lookup -----


def load_brand_library():
    if not BRAND_LIBRARY.exists():
        return {}
    try:
        data = json.loads(BRAND_LIBRARY.read_text())
        return {_norm(k): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def lookup_brand(query: str, library: dict, used: set):
    """Return next unused URL matching this query, or None."""
    q = _norm(query)
    for key, entries in library.items():
        if key in q or q in key:
            for entry in entries:
                url = entry.get("url")
                if url and url not in used:
                    used.add(url)
                    return url, entry.get("type", "image")
    return None, None


# ----- Source 2: yt-dlp YouTube search -----


def search_youtube(query: str):
    """Search YouTube, return URL of best match."""
    try:
        result = subprocess.run(
            ["yt-dlp", f"ytsearch1:{query}", "--get-id", "--no-warnings", "--quiet", "--ignore-errors"],
            capture_output=True, text=True, timeout=30,
        )
        vid = result.stdout.strip().split("\n")[0]
        if vid and len(vid) == 11:
            return f"https://www.youtube.com/watch?v={vid}"
    except Exception:
        pass
    return None


def download_youtube_snippet(url: str, out_path: Path, duration: float = YT_TRIM_SECONDS):
    """Download first `duration` seconds of a YouTube video."""
    try:
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
            "--download-sections", f"*0-{int(duration)}",
            "--force-keyframes-at-cuts",
            "-o", str(out_path),
            "--no-warnings", "--quiet", "--ignore-errors",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return out_path.exists() and out_path.stat().st_size > 10_000
    except Exception:
        return False


# ----- Source 3 & 4: Pexels / Pixabay -----


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


# ----- Source 5: Wikimedia Commons -----


def search_wikimedia_image(query: str):
    try:
        r = requests.get(
            WIKIMEDIA_API,
            params={
                "action": "query", "format": "json", "list": "search",
                "srsearch": query + " filetype:bitmap",
                "srnamespace": 6, "srlimit": 5,
            },
            timeout=20, headers=UA,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0]["title"]
        r2 = requests.get(
            WIKIMEDIA_API,
            params={
                "action": "query", "format": "json", "titles": title,
                "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 1920,
            },
            timeout=20, headers=UA,
        )
        pages = r2.json().get("query", {}).get("pages", {})
        for p in pages.values():
            ii = p.get("imageinfo", [])
            if ii:
                return ii[0].get("thumburl") or ii[0].get("url")
        return None
    except Exception:
        return None


# ----- Source 6: Pollinations AI -----


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


# ----- Shot fetching (multi-source fallback) -----


def fetch_shot(
    idx: int, shot: dict, clips_dir: Path,
    library: dict, used_urls: set,
    pexels_key: str, pixabay_key: str | None,
    enable_youtube: bool = True,
):
    """Try multiple sources to fetch this shot. Returns (path, kind) or (None, None)."""
    query = shot["query"]
    video_path = clips_dir / f"shot_{idx:04d}.mp4"
    image_path = clips_dir / f"shot_{idx:04d}.jpg"

    if video_path.exists():
        return video_path, "video"
    if image_path.exists():
        return image_path, "image"

    # 1. Explicit URL in script
    explicit_url = shot.get("url")
    if explicit_url:
        try:
            ext = "mp4" if any(explicit_url.endswith(s) for s in [".mp4", ".mov", ".webm"]) else "jpg"
            out = video_path if ext == "mp4" else image_path
            download(explicit_url, out)
            return out, ("video" if ext == "mp4" else "image")
        except Exception as e:
            print(f"      [explicit] failed: {e}")

    # 2. Brand library
    url, kind = lookup_brand(query, library, used_urls)
    if url:
        try:
            out = video_path if kind == "video" else image_path
            download(url, out)
            return out, kind
        except Exception as e:
            print(f"      [library] failed for '{query}': {e}")

    sources = shot.get("sources") or ["youtube", "pexels", "pixabay", "wikimedia", "ai"]
    if not enable_youtube and "youtube" in sources:
        sources = [s for s in sources if s != "youtube"]

    for src in sources:
        try:
            if src == "youtube":
                yt_url = search_youtube(query)
                if yt_url and download_youtube_snippet(yt_url, video_path):
                    return video_path, "video"
            elif src == "pexels":
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
    if clip.duration >= target_duration:
        clip = clip.subclipped(0, target_duration)
    else:
        loops = int(target_duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * loops, method="chain").subclipped(0, target_duration)

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

    d = clip.duration
    clip = clip.with_effects([Resize(lambda t, d=d: 1 + (zoom_to - 1) * t / d)])
    return clip


def load_clip(path: Path, kind: str, duration: float):
    if kind == "image":
        clip = ImageClip(str(path)).with_duration(duration)
    else:
        clip = VideoFileClip(str(path)).without_audio()
    return fit_landscape(clip, duration)


def prepare_music(music_path: Path, total_duration: float):
    music = AudioFileClip(str(music_path))
    if music.duration < total_duration:
        loops = int(total_duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops)
    music = music.subclipped(0, total_duration)
    music = music.with_effects([MultiplyVolume(MUSIC_VOLUME)])
    return music


# ----- Main -----


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script-file", required=True)
    parser.add_argument("--no-youtube", action="store_true", help="Disable yt-dlp source")
    args = parser.parse_args()

    pexels_key = os.getenv("PEXELS_API_KEY")
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    if not pexels_key:
        sys.exit("ERROR: PEXELS_API_KEY missing")
    if not pixabay_key:
        print("WARN: PIXABAY_API_KEY not set — falling back to other sources")

    library = load_brand_library()
    print(f"Brand library: {len(library)} entries loaded")

    script = json.loads(Path(args.script_file).read_text())
    slug = script.get("slug") or slugify(script["title"])
    voice = script.get("voice", DEFAULT_VOICE)
    out_dir = ROOT / "clients" / "youtube" / "longform" / slug
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Synthesizing voice ({voice})...")
    voice_path = out_dir / "voice.mp3"
    synthesize_voice(script["voiceover"], voice_path, voice)
    voice_clip = AudioFileClip(str(voice_path))
    total_duration = voice_clip.duration
    print(f"      voiceover: {total_duration:.1f}s ({total_duration/60:.1f} min)")

    shots = script["shots"]
    weights = [s.get("duration", 1) for s in shots]
    weight_sum = sum(weights)
    durations = [(w / weight_sum) * total_duration for w in weights]

    print(f"[2/4] Fetching {len(shots)} shots (multi-source: brand-lib > yt > pexels > pixabay > wikimedia > ai)...")
    used_urls = set()
    video_clips = []
    yt_count = 0
    src_stats = {"library": 0, "youtube": 0, "pexels": 0, "pixabay": 0, "wikimedia": 0, "ai": 0, "failed": 0}

    for i, (shot, dur) in enumerate(zip(shots, durations)):
        query = shot["query"]
        if (i + 1) % 20 == 0 or i < 3 or i == len(shots) - 1:
            print(f"      [{i+1}/{len(shots)}] '{query}' -> {dur:.1f}s")
        path, kind = fetch_shot(
            i, shot, clips_dir, library, used_urls,
            pexels_key, pixabay_key, enable_youtube=not args.no_youtube,
        )
        if not path:
            src_stats["failed"] += 1
            print(f"      [{i+1}] WARN no source matched '{query}'")
            continue
        try:
            clip = load_clip(path, kind, dur)
            video_clips.append(clip)
        except Exception as e:
            src_stats["failed"] += 1
            print(f"      [{i+1}] WARN clip load failed for '{query}': {e}")

    if not video_clips:
        sys.exit("ERROR: no usable clips")

    print(f"      {len(video_clips)}/{len(shots)} clips ready")

    print("[3/4] Compositing timeline...")
    timeline = []
    t = 0.0
    for clip in video_clips:
        timeline.append(clip.with_start(t).with_position("center"))
        t += clip.duration

    video = CompositeVideoClip(timeline, size=(TARGET_W, TARGET_H)).with_duration(min(t, total_duration))

    audio_tracks = [voice_clip]
    music_file = script.get("music_file")
    if music_file:
        music_path = ROOT / music_file
        if music_path.exists():
            print(f"      mixing music: {music_path.name}")
            audio_tracks.append(prepare_music(music_path, total_duration))

    final_audio = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else voice_clip
    video = video.with_audio(final_audio).with_duration(total_duration)

    out_path = out_dir / "video.mp4"
    print(f"[4/4] Encoding -> {out_path} ...")
    video.write_videofile(
        str(out_path),
        fps=30, codec="libx264", audio_codec="aac",
        preset="medium", threads=4, bitrate="6000k", logger=None,
    )
    print(f"\nDone -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
