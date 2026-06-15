# Telugu Video Subtitler — README

A simple tool to burn English subtitles into Telugu videos using Python and FFmpeg.

---

## What It Does

Takes a video file and a subtitle file (SRT), and burns the English subtitles directly onto the video frames to create a new subtitled video.

---

## Files

| File | Purpose |
|------|---------|
| `burn_subtitles.py` | Main script to burn subtitles into a video |
| `burn_video5.py` | Same script but for a specific video (medowVideo4.mp4) |
| `medowVideo1.srt` | Subtitle file for video 1 |
| `medowVideo2.srt` | Subtitle file for video 2 |
| `medowVideo3.srt` | Subtitle file for video 3 |
| `medowVideo5.srt` | Subtitle file for video 4 (medowVideo4.mp4) |

---

## Requirements

### System
- Mac or Windows
- Python 3.10+
- FFmpeg

### Install FFmpeg (Mac)
```bash
brew install ffmpeg
```

### Python Packages
```bash
pip install opencv-python numpy
```

---

## Setup (One Time Only)

```bash
# Go to your Desktop
cd Desktop

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install packages
pip install opencv-python numpy
```

---

## How to Use

### Step 1 — Get your subtitles
Give Claude your subtitles in this format:
```
0:00 - 0:05 → Text here
0:05 - 0:10 → More text here
```
Claude will generate the SRT file for you.

### Step 2 — Save files to Desktop
Save the following to your Desktop:
- Your video file (e.g. `myvideo.mp4`)
- Your SRT file (e.g. `myvideo.srt`)
- The burn script (e.g. `burn_subtitles.py`)

### Step 3 — Update the script
Open `burn_subtitles.py` and check these 3 lines match your filenames:
```python
VIDEO  = "myvideo.mp4"
SRT    = "myvideo.srt"
OUTPUT = "myvideo_subtitled.mp4"
```

### Step 4 — Run it
```bash
cd Desktop
source venv/bin/activate
python3 burn_subtitles.py
```

### Step 5 — Get your output
Find `myvideo_subtitled.mp4` on your Desktop. Done!

---

## SRT File Format

SRT files look like this:
```
1
00:00:00,000 --> 00:00:06,000
First subtitle text here

2
00:00:06,000 --> 00:00:12,000
Second subtitle text here
```

- Each entry has a number, a time range, and the text
- Time format is `HH:MM:SS,milliseconds`
- Blank line between each entry

---

## Saving Files (Important!)

Always use **TextEdit** to save `.py` and `.srt` files:
1. Open TextEdit
2. Click **Format → Make Plain Text**
3. Paste the content
4. **Cmd + S** → name the file → save to Desktop

Or use the terminal to create files directly:
```bash
cat > myfile.py << 'EOF'
# paste code here
EOF
```

---

## Troubleshooting

**"No such file or directory"**
→ Make sure all files (video, SRT, script) are on the Desktop

**File saved as `.srt.txt` or `.py.rtf`**
→ TextEdit added the wrong extension. Fix it:
```bash
mv myfile.srt.txt myfile.srt
mv myfile.py.rtf myfile.py
```

**"source: no such file or directory: venv/bin/activate"**
→ Recreate the venv:
```bash
python3 -m venv venv
source venv/bin/activate
```

**Subtitles look wrong/garbled**
→ The auto-transcription struggled with background noise. Instead, manually provide the subtitles to Claude in the format above and Claude will generate the SRT file for you.

---

## Every Time You Open a New Terminal

Always activate the virtual environment first:
```bash
source venv/bin/activate
```
You'll see `(venv)` at the start of the terminal line when it's active.
