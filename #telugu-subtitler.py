#telugu-subtitler
"""
Telugu Video Subtitler
Extracts audio → transcribes Telugu → translates to English → burns subtitles into video.

Dependencies: see README / setup instructions below.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Third-party ──────────────────────────────────────────────────────────────
try:
    import whisper
except ImportError:
    sys.exit("whisper not found. Run: pip install openai-whisper")

try:
    from deep_translator import GoogleTranslator
except ImportError:
    sys.exit("deep-translator not found. Run: pip install deep-translator")


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUDIO EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_audio(video_path: str, audio_path: str) -> None:
    """Extract 16 kHz mono WAV from video using FFmpeg."""
    print(f"[1/5] Extracting audio from: {video_path}")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                  # no video
        "-acodec", "pcm_s16le", # PCM WAV
        "-ar", "16000",         # 16 kHz – optimal for Whisper
        "-ac", "1",             # mono
        audio_path,
    ]
    _run(cmd, "Audio extraction failed")
    print(f"    → Audio saved: {audio_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRANSCRIPTION  (Whisper)
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_audio(audio_path: str, model_size: str = "medium") -> list[dict]:
    """
    Transcribe audio with Whisper.
    Returns list of segment dicts: {start, end, text}
    """
    print(f"[2/5] Transcribing with Whisper model='{model_size}' (Telugu)…")
    model = whisper.load_model(model_size)
    result = model.transcribe(
        audio_path,
        language="te",          # Telugu ISO-639 code
        task="transcribe",      # keep original language text
        verbose=False,
        fp16=False,             # safer across CPU/GPU
        condition_on_previous_text=True,
        word_timestamps=False,
    )
    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result["segments"]
        if s["text"].strip()
    ]
    print(f"    → {len(segments)} segments transcribed.")
    return segments


# ─────────────────────────────────────────────────────────────────────────────
# 3. TRANSLATION  (deep-translator → Google Translate)
# ─────────────────────────────────────────────────────────────────────────────

def translate_segments(segments: list[dict], batch_size: int = 30) -> list[dict]:
    """
    Translate Telugu segments to English in batches.
    Returns new list with 'translated' key added.
    """
    print(f"[3/5] Translating {len(segments)} segments (te → en)…")
    translator = GoogleTranslator(source="te", target="en")
    translated = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        texts = [s["text"] for s in batch]

        # Join with a rare delimiter, translate once, split back
        delimiter = " ||||| "
        joined = delimiter.join(texts)
        try:
            result = translator.translate(joined)
            parts = result.split("|||||")
            if len(parts) != len(texts):
                # Fallback: translate one by one
                parts = [translator.translate(t) for t in texts]
        except Exception as e:
            print(f"    [!] Batch {i//batch_size+1} failed ({e}); retrying individually…")
            parts = []
            for t in texts:
                try:
                    parts.append(translator.translate(t))
                except Exception:
                    parts.append(t)  # keep original on failure

        for seg, eng in zip(batch, parts):
            translated.append({**seg, "translated": eng.strip() if eng else seg["text"]})

        print(f"    → Translated {min(i+batch_size, len(segments))}/{len(segments)}")

    return translated


# ─────────────────────────────────────────────────────────────────────────────
# 4. SRT GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp HH:MM:SS,mmm."""
    ms = int(round((seconds % 1) * 1000))
    s  = int(seconds)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments: list[dict], max_chars_per_line: int = 42) -> str:
    """Build SRT content string from translated segments."""
    lines = []
    for i, seg in enumerate(segments, start=1):
        text = seg["translated"]
        # Wrap long lines at word boundaries
        wrapped = _wrap_text(text, max_chars_per_line)
        lines.append(str(i))
        lines.append(f"{seconds_to_srt_time(seg['start'])} --> {seconds_to_srt_time(seg['end'])}")
        lines.append(wrapped)
        lines.append("")          # blank line between entries
    return "\n".join(lines)


def _wrap_text(text: str, limit: int) -> str:
    """Wrap text at word boundaries up to `limit` chars per line (max 2 lines)."""
    if len(text) <= limit:
        return text
    words = text.split()
    line1, line2 = [], []
    for w in words:
        candidate = " ".join(line1 + [w])
        if len(candidate) <= limit:
            line1.append(w)
        else:
            line2.append(w)
    result = " ".join(line1)
    if line2:
        result += "\n" + " ".join(line2)
    return result


def write_srt(srt_content: str, path: str) -> None:
    Path(path).write_text(srt_content, encoding="utf-8")
    print(f"[4/5] SRT written: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. BURN SUBTITLES INTO VIDEO  (FFmpeg)
# ─────────────────────────────────────────────────────────────────────────────

def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_size: int = 22,
    font_color: str = "white",
    outline_color: str = "black",
    font_name: str = "Arial",
) -> None:
    """Burn SRT subtitles into video with FFmpeg subtitles filter."""
    print(f"[5/5] Burning subtitles into video…")

    # Use absolute path and escape for FFmpeg
    abs_srt = str(Path(srt_path).resolve())
    # On Mac, colons in paths need escaping
    safe_srt = abs_srt.replace("\\", "/").replace(":", "\\:")

    vf = f"subtitles={safe_srt}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]
    _run(cmd, "Subtitle burning failed")
    print(f"\n✅ Done! Output video: {output_path}")

def _subtitle_style(font: str, size: int, color: str, outline: str) -> str:
    color_map = {
        "white":  "FFFFFF",
        "yellow": "00FFFF",     # FFmpeg uses BGR hex
        "black":  "000000",
        "cyan":   "FFFF00",
    }
    fc = color_map.get(color.lower(), "FFFFFF")
    oc = color_map.get(outline.lower(), "000000")
    return (
        f"FontName={font},FontSize={size},"
        f"PrimaryColour=&H00{fc}&,"
        f"OutlineColour=&H00{oc}&,"
        f"BorderStyle=1,Outline=1.5,Shadow=0.5,Alignment=2"
    )


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], error_msg: str) -> None:
    """Run a subprocess command, exit on failure."""
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    except FileNotFoundError:
        sys.exit("FFmpeg not found. Install it and ensure it's on your PATH.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] {error_msg}")
        print(e.stderr.decode(errors="replace"))
        sys.exit(1)


def check_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit(
            "FFmpeg is not installed or not on PATH.\n"
            "  Mac:     brew install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def process_video(
    input_video: str,
    output_video: str,
    srt_out: str | None,
    model_size: str,
    font_size: int,
    font_color: str,
    font_name: str,
) -> None:
    check_ffmpeg()

    input_path = Path(input_video)
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_video}")

    # Auto-name outputs if not specified
    stem = input_path.stem
    if not output_video:
        output_video = str(input_path.parent / f"{stem}_subtitled.mp4")
    if not srt_out:
        srt_out = str(input_path.parent / f"{stem}.srt")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.wav")

        # Steps 1-5
        extract_audio(input_video, audio_path)
        segments = transcribe_audio(audio_path, model_size)

        if not segments:
            sys.exit("No speech detected in the audio.")

        segments = translate_segments(segments)
        srt_content = build_srt(segments)

        # Write SRT to final location (not tmp, so user keeps it)
        write_srt(srt_content, srt_out)

        burn_subtitles(
            video_path=input_video,
            srt_path=srt_out,
            output_path=output_video,
            font_size=font_size,
            font_color=font_color,
            font_name=font_name,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe Telugu video → English subtitles → burn into video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python telugu_subtitler.py movie.mp4
  python telugu_subtitler.py movie.mp4 -o out.mp4 --model large --font-size 26
  python telugu_subtitler.py movie.mp4 --srt-only          # just export SRT
  python telugu_subtitler.py movie.mp4 --font-color yellow --font-name "DejaVu Sans"
        """,
    )
    parser.add_argument("input",            help="Path to input video file")
    parser.add_argument("-o", "--output",   default="", help="Output video path (default: <input>_subtitled.mp4)")
    parser.add_argument("--srt",            default="", dest="srt_out", help="Path to save SRT file (default: <input>.srt)")
    parser.add_argument("--srt-only",       action="store_true", help="Only generate SRT; skip burning into video")
    parser.add_argument("--model",          default="medium",
                        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
                        help="Whisper model size (default: medium)")
    parser.add_argument("--font-size",      type=int, default=22, help="Subtitle font size (default: 22)")
    parser.add_argument("--font-color",     default="white",
                        choices=["white", "yellow", "black", "cyan"],
                        help="Subtitle font color (default: white)")
    parser.add_argument("--font-name",      default="Arial", help="Font name (default: Arial)")

    args = parser.parse_args()

    if args.srt_only:
        # Abbreviated pipeline: skip burn step
        check_ffmpeg()
        input_path = Path(args.input)
        srt_out = args.srt_out or str(input_path.parent / f"{input_path.stem}.srt")
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.wav")
            extract_audio(args.input, audio_path)
            segments = transcribe_audio(audio_path, args.model)
            segments = translate_segments(segments)
            srt_content = build_srt(segments)
            write_srt(srt_content, srt_out)
        print(f"\n✅ SRT exported: {srt_out}")
    else:
        process_video(
            input_video=args.input,
            output_video=args.output,
            srt_out=args.srt_out,
            model_size=args.model,
            font_size=args.font_size,
            font_color=args.font_color,
            font_name=args.font_name,
        )


if __name__ == "__main__":
    main()

