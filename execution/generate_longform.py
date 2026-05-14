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


# ----- Source 2: yt-dlp YouTube search (V3: filtered, top-5, sponsorblock) -----


def search_youtube(query: str, n_results: int = 5):
    """Search YouTube. Filter: 30s-30min, no Shorts. Return URL of best match."""
    try:
        result = subprocess.run(
            [
                "yt-dlp", f"ytsearch{n_results}:{query}",
                "--match-filters", "duration > 30 & duration < 1800",
                "--get-id", "--no-warnings", "--quiet", "--ignore-errors",
            ],
            capture_output=True, text=True, timeout=60,
        )
        ids = [i for i in result.stdout.strip().split("\n") if len(i) == 11]
        if ids:
            return f"https://www.youtube.com/watch?v={ids[0]}"
    except Exception:
        pass
    return None


def download_youtube_snippet(url: str, out_path: Path, start: int = 15, duration: float = 10):
    """Download `duration` sec from offset `start` (skips intros). SponsorBlock removes ads/sponsors."""
    end = start + int(duration)
    try:
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts",
            "--sponsorblock-remove", "sponsor,intro,outro,selfpromo,preview",
            "-o", str(out_path),
            "--no-warnings", "--quiet", "--ignore-errors",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if out_path.exists() and out_path.stat().st_size > 10_000:
            return True
        # Fallback: try without sponsorblock if it failed
        cmd_simple = [c for c in cmd if "sponsorblock" not in c and c not in ("sponsor,intro,outro,selfpromo,preview",)]
        result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=180)
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
    """Try multiple sources to fetch this shot. Returns (path, kind, source) or (None, None, None).

    V3: supports multi-query via `queries` list — tries each query through all sources.
    """
    queries = shot.get("queries") or [shot.get("query", "")]
    if isinstance(queries, str):
        queries = [queries]
    video_path = clips_dir / f"shot_{idx:04d}.mp4"
    image_path = clips_dir / f"shot_{idx:04d}.jpg"

    if video_path.exists():
        return video_path, "video", "cache"
    if image_path.exists():
        return image_path, "image", "cache"

    # 1. Explicit URL in script
    explicit_url = shot.get("url")
    if explicit_url:
        try:
            ext = "mp4" if any(explicit_url.endswith(s) for s in [".mp4", ".mov", ".webm"]) else "jpg"
            out = video_path if ext == "mp4" else image_path
            download(explicit_url, out)
            return out, ("video" if ext == "mp4" else "image"), "explicit"
        except Exception as e:
            print(f"      [explicit] failed: {e}")

    # 2. Brand library (try each query)
    for q in queries:
        url, kind = lookup_brand(q, library, used_urls)
        if url:
            try:
                out = video_path if kind == "video" else image_path
                download(url, out)
                return out, kind, "library"
            except Exception as e:
                print(f"      [library] failed for '{q}': {e}")

    sources = shot.get("sources") or ["youtube", "pexels", "pixabay", "wikimedia", "ai"]
    if not enable_youtube and "youtube" in sources:
        sources = [s for s in sources if s != "youtube"]

    for q in queries:
        for src in sources:
            try:
                if src == "youtube":
                    yt_url = search_youtube(q)
                    if yt_url and download_youtube_snippet(yt_url, video_path):
                        return video_path, "video", "youtube"
                elif src == "pexels":
                    url = search_pexels(q, pexels_key)
                    if url:
                        download(url, video_path)
                        return video_path, "video", "pexels"
                elif src == "pixabay":
                    url = search_pixabay_video(q, pixabay_key)
                    if url:
                        download(url, video_path)
                        return video_path, "video", "pixabay"
                elif src == "pixabay_image":
                    url = search_pixabay_image(q, pixabay_key)
                    if url:
                        download(url, image_path)
                        return image_path, "image", "pixabay_image"
                elif src == "wikimedia":
                    url = search_wikimedia_image(q)
                    if url:
                        download(url, image_path)
                        return image_path, "image", "wikimedia"
                elif src == "ai":
                    url = pollinations_image_url(q)
                    download(url, image_path)
                    return image_path, "image", "ai"
            except Exception as e:
                print(f"      [{src}] failed for '{q}': {e}")
                continue

    return None, None, None


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

    print(f"[2/4] Fetching + processing {len(shots)} shots (streaming to disk to conserve RAM)...")
    used_urls = set()
    processed_paths = []
    src_stats = {"explicit": 0, "library": 0, "youtube": 0, "pexels": 0, "pixabay": 0, "pixabay_image": 0, "wikimedia": 0, "ai": 0, "cache": 0, "failed": 0}
    processed_dir = out_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    for i, (shot, dur) in enumerate(zip(shots, durations)):
        queries = shot.get("queries") or [shot.get("query", "")]
        primary_query = queries[0] if isinstance(queries, list) else queries
        if (i + 1) % 20 == 0 or i < 3 or i == len(shots) - 1:
            print(f"      [{i+1}/{len(shots)}] '{primary_query}' -> {dur:.1f}s")

        processed_path = processed_dir / f"p_{i:04d}.mp4"
        if processed_path.exists() and processed_path.stat().st_size > 5000:
            processed_paths.append(processed_path)
            src_stats["cache"] += 1
            continue

        path, kind, source = fetch_shot(
            i, shot, clips_dir, library, used_urls,
            pexels_key, pixabay_key, enable_youtube=not args.no_youtube,
        )
        if not path:
            src_stats["failed"] += 1
            print(f"      [{i+1}] WARN no source matched '{primary_query}'")
            continue
        try:
            clip = load_clip(path, kind, dur)
            # Render this clip to disk immediately and release memory
            clip.write_videofile(
                str(processed_path),
                fps=30, codec="libx264", audio=False,
                preset="ultrafast", threads=2, bitrate="5000k",
                logger=None,
            )
            try:
                clip.close()
            except Exception:
                pass
            processed_paths.append(processed_path)
            src_stats[source] = src_stats.get(source, 0) + 1
        except Exception as e:
            src_stats["failed"] += 1
            print(f"      [{i+1}] WARN process failed for '{primary_query}': {e}")

    if not processed_paths:
        sys.exit("ERROR: no usable clips")

    print(f"      {len(processed_paths)}/{len(shots)} clips processed to disk")
    print(f"      sources: {dict((k, v) for k, v in src_stats.items() if v > 0)}")

    print("[3/4] Stitching with ffmpeg concat (streaming, low memory)...")
    concat_file = out_dir / "concat.txt"
    with concat_file.open("w") as f:
        for p in processed_paths:
            f.write(f"file '{p.resolve()}'\n")

    silent_video = out_dir / "_video_no_audio.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-loglevel", "error",
            str(silent_video),
        ],
        check=True,
    )

    # Release voice_clip — ffmpeg will pull straight from voice.mp3
    try:
        voice_clip.close()
    except Exception:
        pass

    print("[4/4] Muxing audio + normalizing + final encode...")
    out_path = out_dir / "video.mp4"
    music_path = None
    music_file = script.get("music_file")
    if music_file:
        candidate = ROOT / music_file
        if candidate.exists():
            music_path = candidate
            print(f"      mixing music: {music_path.name}")

    # Build the audio-filter graph
    if music_path:
        audio_inputs = ["-i", str(voice_path), "-stream_loop", "-1", "-i", str(music_path)]
        # Loop music; lower its volume; mix with voice; then loudnorm
        af = (
            f"[1:a]volume={MUSIC_VOLUME}[m];"
            f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[mixed];"
            f"[mixed]loudnorm=I=-16:LRA=11:TP=-1.5[aout]"
        )
    else:
        audio_inputs = ["-i", str(voice_path)]
        af = "[0:a]loudnorm=I=-16:LRA=11:TP=-1.5[aout]"

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_video),
        *audio_inputs,
        "-filter_complex", af,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(out_path),
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    silent_video.unlink(missing_ok=True)

    print(f"\nDone -> {out_path} ({out_path.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
