#!/usr/bin/env python3
"""
Telugu → English Subtitle Pipeline
Usage: python3 subtitle_pipeline.py myvideo.mp4
"""

import re
import subprocess
import os
import sys
import cv2
import numpy as np
import soundfile as sf
import noisereduce as nr
import whisper
from deep_translator import GoogleTranslator
from pathlib import Path

# ── SETTINGS — change these if needed ────────────────────────
MODEL_SIZE  = "large-v3"   # or "medium" if too slow
SOURCE_LANG = "te"         # Telugu
TARGET_LANG = "en"         # English
FONT_SCALE  = 0.7
FONT_COLOR  = (255, 255, 255)   # white
OUTLINE     = (0, 0, 0)         # black
# ─────────────────────────────────────────────────────────────


# ── STEP 1: EXTRACT AUDIO ────────────────────────────────────
def extract_audio(video_path, out_path):
    print("\n[1/6] Extracting audio...")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        out_path
    ], check=True, stderr=subprocess.DEVNULL)
    print(f"    → Saved: {out_path}")


# ── STEP 2: DENOISE ──────────────────────────────────────────
def denoise_audio(in_path, out_path):
    print("\n[2/6] Denoising audio...")
    data, rate = sf.read(in_path)
    noise_sample = data[:int(rate * 0.5)]
    clean = nr.reduce_noise(y=data, sr=rate, y_noise=noise_sample, prop_decrease=0.8)
    sf.write(out_path, clean, rate)
    print(f"    → Saved: {out_path}")


# ── STEP 3: TRANSCRIBE ───────────────────────────────────────
def transcribe(audio_path):
    print(f"\n[3/6] Transcribing with Whisper ({MODEL_SIZE})...")
    model = whisper.load_model(MODEL_SIZE)
    result = model.transcribe(
        audio_path,
        language=SOURCE_LANG,
        task="transcribe",
        fp16=False,
        condition_on_previous_text=True,
        verbose=False,
    )
    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result["segments"] if s["text"].strip()
    ]
    print(f"    → {len(segments)} segments transcribed.")
    return segments


# ── STEP 4: TRANSLATE ────────────────────────────────────────
def translate(segments):
    print(f"\n[4/6] Translating {len(segments)} segments...")
    translator = GoogleTranslator(source=SOURCE_LANG, target=TARGET_LANG)
    for i, seg in enumerate(segments):
        try:
            seg["translated"] = translator.translate(seg["text"]).strip()
        except Exception:
            seg["translated"] = seg["text"]
        print(f"    [{i+1}/{len(segments)}] {seg['translated']}")
    return segments


# ── STEP 5: WRITE SRT ────────────────────────────────────────
def to_srt_time(s):
    ms = int((s % 1) * 1000)
    s  = int(s)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def write_srt(segments, srt_path):
    print(f"\n[5/6] Writing SRT file...")
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [
            str(i),
            f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}",
            seg["translated"],
            ""
        ]
    Path(srt_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"    → Saved: {srt_path}")


# ── STEP 6: BURN SUBTITLES ───────────────────────────────────
def parse_srt(srt_path):
    content = Path(srt_path).read_text(encoding="utf-8")
    pattern = re.compile(
        r'\d+\s+'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+'
        r'(.*?)(?=\n\n|\Z)', re.DOTALL
    )
    subs = []
    for m in pattern.finditer(content):
        start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
        end   = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
        text  = m.group(9).strip().replace("\n", " ")
        subs.append((start, end, text))
    return subs

def get_subtitle(subs, t):
    for start, end, text in subs:
        if start <= t <= end:
            return text
    return None

def draw_text(frame, text):
    font  = cv2.FONT_HERSHEY_SIMPLEX
    h, w  = frame.shape[:2]
    words = text.split()
    lines, line = [], []
    for word in words:
        test = " ".join(line + [word])
        (tw, _), _ = cv2.getTextSize(test, font, FONT_SCALE, 2)
        if tw > w * 0.9 and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))

    line_h  = int(cv2.getTextSize("A", font, FONT_SCALE, 2)[0][1] * 2.5)
    y_start = h - 20 - line_h * (len(lines) - 1)

    for i, ln in enumerate(lines):
        (tw, _), _ = cv2.getTextSize(ln, font, FONT_SCALE, 2)
        x = (w - tw) // 2
        y = y_start + i * line_h
        cv2.putText(frame, ln, (x-1, y-1), font, FONT_SCALE, OUTLINE, 4, cv2.LINE_AA)
        cv2.putText(frame, ln, (x+1, y+1), font, FONT_SCALE, OUTLINE, 4, cv2.LINE_AA)
        cv2.putText(frame, ln, (x, y),     font, FONT_SCALE, FONT_COLOR, 2, cv2.LINE_AA)
    return frame

def burn_subtitles(video_path, srt_path, output_path):
    print(f"\n[6/6] Burning subtitles into video...")
    subs    = parse_srt(srt_path)
    cap     = cv2.VideoCapture(video_path)
    fps     = cap.get(cv2.CAP_PROP_FPS)
    width   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    tmp     = output_path + "_tmp.mp4"
    out     = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    frame_num = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        text = get_subtitle(subs, frame_num / fps)
        if text:
            frame = draw_text(frame, text)
        out.write(frame)
        frame_num += 1
        if frame_num % 300 == 0:
            print(f"    Frame {frame_num}/{total} ({frame_num/total*100:.1f}%)", flush=True)

    cap.release()
    out.release()

    print("    Merging audio...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", tmp, "-i", video_path,
        "-c:v", "copy",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:a", "copy", "-shortest",
        output_path
    ], check=True, stderr=subprocess.DEVNULL)
    os.remove(tmp)
    print(f"\n✅ Done! Output: {output_path}")


# ── MAIN ─────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 subtitle_pipeline.py myvideo.mp4")
        sys.exit(1)

    video   = sys.argv[1]
    stem    = Path(video).stem
    raw_wav = stem + "_raw.wav"
    cln_wav = stem + "_clean.wav"
    srt     = stem + ".srt"
    output  = stem + "_subtitled.mp4"

    extract_audio(video, raw_wav)
    denoise_audio(raw_wav, cln_wav)
    segments = transcribe(cln_wav)
    segments = translate(segments)
    write_srt(segments, srt)
    burn_subtitles(video, srt, output)

    # Cleanup temp wav files
    for f in [raw_wav, cln_wav]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    main()