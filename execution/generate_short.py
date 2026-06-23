#!/usr/bin/env python3
"""Generate a YouTube Short with auto-burned captions, Ken Burns motion, and a hook card.

Pipeline:
  1. Synthesize voiceover (ElevenLabs Adam if ELEVENLABS_API_KEY set, else Edge TTS).
  2. Get word-level timings.
  3. Download stock clips from Pexels.
  4. Crop to 1080x1920 + apply Ken Burns zoom.
  5. Assemble video with voiceover.
  6. Generate ASS subtitles (bold white + yellow emphasis + top hook card).
  7. ffmpeg burn-in -> final base.mp4.

Usage:
  python execution/generate_short.py --script-file clients/youtube/scripts/honey-never-spoils.json
"""

import argparse
import asyncio
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import requests
from dotenv import load_dotenv
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.Resize import Resize

load_dotenv()

PEXELS_API = "https://api.pexels.com/videos/search"
TARGET_W, TARGET_H = 1080, 1920
ROOT = Path(__file__).resolve().parent.parent

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
EDGE_VOICE = "en-US-GuyNeural"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

WORDS_PER_LINE = 3
KEN_BURNS_ZOOM = 1.10


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


# ----- Voice synthesis -----


def _chars_to_words(chars, starts, ends):
    """Group ElevenLabs character timings into (word, start, end) tuples."""
    words, buf, w_start, w_end = [], "", None, None
    for c, s, e in zip(chars, starts, ends):
        if c.isalnum() or c in "'-":
            if not buf:
                w_start = s
            buf += c
            w_end = e
        else:
            if buf:
                words.append((buf, w_start, w_end))
                buf, w_start, w_end = "", None, None
    if buf:
        words.append((buf, w_start, w_end))
    return words


def _voice_elevenlabs(text: str, out_path: Path, api_key: str):
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=api_key)
    result = client.text_to_speech.convert_with_timestamps(
        voice_id=ADAM_VOICE_ID,
        text=text,
        model_id=ELEVENLABS_MODEL,
        output_format="mp3_44100_128",
    )
    audio_b64 = getattr(result, "audio_base_64", None) or getattr(result, "audio_base64", None)
    if not audio_b64:
        raise RuntimeError(f"ElevenLabs response missing audio. Fields: {list(vars(result).keys())}")
    out_path.write_bytes(base64.b64decode(audio_b64))
    alignment = result.alignment
    return _chars_to_words(
        alignment.characters,
        alignment.character_start_times_seconds,
        alignment.character_end_times_seconds,
    )


def _voice_edge(text: str, out_path: Path):
    async def run():
        sub_maker = edge_tts.SubMaker()
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    sub_maker.feed(chunk)
        return sub_maker

    sub_maker = asyncio.run(run())
    words = []
    for cue in sub_maker.cues:
        start = cue.start.total_seconds()
        end = cue.end.total_seconds()
        for w in cue.content.split():
            words.append((w, start, end))
    return words


def synthesize_voice(text: str, out_path: Path, use_elevenlabs: bool = False):
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if use_elevenlabs and api_key:
        print("  using ElevenLabs (Adam)")
        return _voice_elevenlabs(text, out_path, api_key)
    print("  using Edge TTS (Guy)")
    return _voice_edge(text, out_path)


# ----- Pexels footage -----


def search_pexels_video(query: str, api_key: str):
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


def download(url: str, out_path: Path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


# ----- Video processing -----


def process_clip(raw, target_duration: float, zoom_to: float = KEN_BURNS_ZOOM):
    if raw.duration >= target_duration:
        clip = raw.subclipped(0, target_duration)
    else:
        loops = int(target_duration / raw.duration) + 1
        clip = concatenate_videoclips([raw] * loops, method="chain").subclipped(0, target_duration)

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


# ----- Subtitles (ASS) -----


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    cs = int(round((s - int(s)) * 100))
    if cs == 100:
        cs = 0
        s = int(s) + 1
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def _mark_emphasis(words, emphasis_phrases):
    norms = [_norm(w[0]) for w in words]
    flags = [False] * len(words)
    for phrase in emphasis_phrases or []:
        pw = _norm(phrase).split()
        n = len(pw)
        if n == 0:
            continue
        for i in range(len(norms) - n + 1):
            if norms[i : i + n] == pw:
                for j in range(i, i + n):
                    flags[j] = True
    return flags


def generate_ass(words, emphasis, hook_text, out_path: Path):
    flags = _mark_emphasis(words, emphasis)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Anton,110,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,2,2,60,60,360,1
Style: Hook,Anton,130,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,3,8,80,80,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook_text:
        hook = hook_text.upper().replace("\n", " ")
        lines.append(f"Dialogue: 1,{_fmt_ass_time(0)},{_fmt_ass_time(2.2)},Hook,,0,0,0,,{hook}")

    for i in range(0, len(words), WORDS_PER_LINE):
        group = words[i : i + WORDS_PER_LINE]
        start = group[0][1]
        end = group[-1][2]
        parts = []
        for j, (w, _, _) in enumerate(group):
            text = w.upper()
            if flags[i + j]:
                parts.append(r"{\c&H00FFFF&}" + text + r"{\c&HFFFFFF&}")
            else:
                parts.append(text)
        lines.append(
            f"Dialogue: 0,{_fmt_ass_time(start)},{_fmt_ass_time(end)},Caption,,0,0,0,,{' '.join(parts)}"
        )
    out_path.write_text(header + "\n".join(lines) + "\n")


# ----- Main -----


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script-file", required=True)
    args = parser.parse_args()

    pexels_key = os.getenv("PEXELS_API_KEY")
    if not pexels_key:
        sys.exit("ERROR: PEXELS_API_KEY missing in .env")

    script = json.loads(Path(args.script_file).read_text())
    slug = script.get("slug") or slugify(script["title"])
    out_dir = ROOT / "clients" / "youtube" / slug
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    print("[1/6] Voice + timings...")
    voice_path = out_dir / "voice.mp3"
    words = synthesize_voice(
        script["voiceover"],
        voice_path,
        use_elevenlabs=bool(script.get("use_elevenlabs", False)),
    )
    voice_clip = AudioFileClip(str(voice_path))
    total = voice_clip.duration
    print(f"      {total:.1f}s, {len(words)} words")

    shots = script["shots"]
    weights = [s.get("duration", 1) for s in shots]
    durations = [(w / sum(weights)) * total for w in weights]

    print(f"[2/6] Footage ({len(shots)} clips)...")
    processed = []
    for i, (shot, dur) in enumerate(zip(shots, durations)):
        path = clips_dir / f"shot_{i:02d}.mp4"
        if not path.exists():
            url = search_pexels_video(shot["query"], pexels_key)
            if not url:
                print(f"      WARN no results for '{shot['query']}'")
                continue
            download(url, path)
        raw = VideoFileClip(str(path)).without_audio()
        processed.append(process_clip(raw, dur))

    if not processed:
        sys.exit("ERROR: no clips usable")

    print("[3/6] Compositing with Ken Burns motion...")
    timeline = []
    t = 0.0
    for clip in processed:
        timeline.append(clip.with_start(t).with_position("center"))
        t += clip.duration

    video = CompositeVideoClip(timeline, size=(TARGET_W, TARGET_H)).with_duration(min(t, total))
    video = video.with_audio(voice_clip).with_duration(total)

    temp_mp4 = out_dir / "_pre_subs.mp4"
    print(f"[4/6] Encoding video (no subs yet) -> {temp_mp4.name}")
    video.write_videofile(
        str(temp_mp4),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )

    if script.get("no_captions"):
        out_path = out_dir / "base.mp4"
        print(f"[5/5] no_captions=true — finalizing without subtitles -> {out_path}")
        temp_mp4.rename(out_path)
    else:
        print("[5/6] Generating captions (.ass)...")
        ass_path = out_dir / "captions.ass"
        hook = script.get("hook") or script.get("title", "").split(":")[0]
        generate_ass(words, script.get("emphasis", []), hook, ass_path)

        out_path = out_dir / "base.mp4"
        print(f"[6/6] Burning captions -> {out_path}")
        ass_escaped = str(ass_path).replace("\\", "/").replace(":", r"\:")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(temp_mp4),
                "-vf",
                f"subtitles={ass_escaped}",
                "-c:a",
                "copy",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-loglevel",
                "error",
                str(out_path),
            ],
            check=True,
        )
        temp_mp4.unlink(missing_ok=True)

    print(f"\nDone -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
