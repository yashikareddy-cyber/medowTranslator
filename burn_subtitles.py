#!/usr/bin/env python3
import re
import subprocess
import os
import sys
import cv2
import numpy as np

# ── CHANGE THESE IF NEEDED ───────────────────────────────────
VIDEO  = "medowVideo5.MP4"
SRT    = "medowVideo5.srt"
OUTPUT = "medowVideo5_subtitled.mp4"
# ─────────────────────────────────────────────────────────────

def parse_srt(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r'\d+\s+'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+'
        r'(.*?)(?=\n\n|\Z)',
        re.DOTALL
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
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness  = 2
    h, w       = frame.shape[:2]

    words = text.split()
    lines, line = [], []
    for word in words:
        test = " ".join(line + [word])
        (tw, _), _ = cv2.getTextSize(test, font, font_scale, thickness)
        if tw > w * 0.9 and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))

    line_h = int(cv2.getTextSize("A", font, font_scale, thickness)[0][1] * 2.5)
    y_start = h - 20 - line_h * (len(lines) - 1)

    for i, ln in enumerate(lines):
        (tw, th), _ = cv2.getTextSize(ln, font, font_scale, thickness)
        x = (w - tw) // 2
        y = y_start + i * line_h
        cv2.putText(frame, ln, (x-1, y-1), font, font_scale, (0,0,0), thickness+2, cv2.LINE_AA)
        cv2.putText(frame, ln, (x+1, y+1), font, font_scale, (0,0,0), thickness+2, cv2.LINE_AA)
        cv2.putText(frame, ln, (x, y),     font, font_scale, (255,255,255), thickness, cv2.LINE_AA)
    return frame

print("Starting...")
subs = parse_srt(SRT)
print(f"Loaded {len(subs)} subtitles.")

cap    = cv2.VideoCapture(VIDEO)
fps    = cap.get(cv2.CAP_PROP_FPS)
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {width}x{height} @ {fps:.2f}fps, {total} frames")

tmp_video = "_tmp_noaudio.mp4"
out = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

frame_num = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    t    = frame_num / fps
    text = get_subtitle(subs, t)
    if text:
        frame = draw_text(frame, text)
    out.write(frame)
    frame_num += 1
    if frame_num % 300 == 0:
        pct = frame_num / total * 100
        print(f"  Frame {frame_num}/{total} ({pct:.1f}%)", flush=True)

cap.release()
out.release()
print("Frames done. Merging audio...")

subprocess.run([
    "ffmpeg", "-y",
    "-i", tmp_video,
    "-i", VIDEO,
    "-c:v", "copy",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-c:a", "copy",
    "-shortest",
    OUTPUT
], check=True)

os.remove(tmp_video)
print(f"\n✅ Done! Output: {OUTPUT}")
