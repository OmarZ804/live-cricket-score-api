import os
import math
import subprocess
from io import BytesIO
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Indus Gamers Video Generator")

# --- Fonts helper ---
def get_font(size: int, bold: bool = False):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

# --- Request Models ---
class Winner(BaseModel):
    name: str
    points: float
    rank: int
    captain: Optional[str] = None

class VideoRequest(BaseModel):
    type: str  # "match_reminder" or "match_podium"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    series: Optional[str] = None
    team_a: Optional[str] = None
    team_b: Optional[str] = None
    venue: Optional[str] = None
    deadline: Optional[str] = None
    result: Optional[str] = None
    winners: Optional[List[Winner]] = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "indus-gamers-video", "engine": "ffmpeg-h264"}

# --- Draw Frame Functions (1080x1080) ---

def draw_reminder_frame(req: VideoRequest, frame_idx: int, total_frames: int) -> Image.Image:
    W, H = 1080, 1080
    t = frame_idx / total_frames  # 0.0 to 1.0

    # Background gradient (deep navy to emerald)
    img = Image.new("RGB", (W, H), (10, 15, 30))
    draw = ImageDraw.Draw(img)

    # Ambient radial circles
    glow_alpha = int(40 + 20 * math.sin(t * math.pi * 4))
    draw.ellipse([-200, -200, 600, 600], fill=(16, 185, 129, glow_alpha))
    draw.ellipse([600, 600, 1400, 1400], fill=(6, 78, 59, glow_alpha))

    # Top Brand Header
    draw.text((W // 2, 80), "INDUS GAMERS", font=get_font(34, bold=True), fill=(16, 185, 129), anchor="mm")
    draw.text((W // 2, 130), "FANTASY CRICKET • MATCH REMINDER", font=get_font(24), fill=(156, 163, 175), anchor="mm")

    # Series & Venue
    series_txt = (req.series or "Upcoming Match").upper()
    if len(series_txt) > 42:
        series_txt = series_txt[:40] + "..."
    draw.text((W // 2, 230), series_txt, font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")

    if req.venue:
        draw.text((W // 2, 275), req.venue[:50], font=get_font(22), fill=(156, 163, 175), anchor="mm")

    # Team Clash Boxes
    team_a = req.team_a or "Team A"
    team_b = req.team_b or "Team B"

    # Slide-in animation for team cards (ease-out during first second)
    slide = min(1.0, frame_idx / 25.0)
    ease = 1.0 - math.pow(1.0 - slide, 3)

    offset_a = int((1.0 - ease) * -400)
    offset_b = int((1.0 - ease) * 400)

    # Team A Card
    draw.rounded_rectangle([100 + offset_a, 360, 470 + offset_a, 620], radius=24, fill=(17, 24, 39), outline=(55, 65, 81), width=3)
    draw.ellipse([235 + offset_a, 400, 335 + offset_a, 500], fill=(30, 41, 59))
    draw.text((285 + offset_a, 450), team_a[:3].upper(), font=get_font(36, bold=True), fill=(16, 185, 129), anchor="mm")
    draw.text((285 + offset_a, 550), team_a, font=get_font(30, bold=True), fill=(255, 255, 255), anchor="mm")

    # VS badge with pulsating ring
    pulse = 1.0 + 0.12 * math.sin(t * math.pi * 8)
    radius_vs = int(48 * pulse)
    draw.ellipse([540 - radius_vs, 490 - radius_vs, 540 + radius_vs, 490 + radius_vs], fill=(245, 158, 11))
    draw.text((540, 490), "VS", font=get_font(32, bold=True), fill=(0, 0, 0), anchor="mm")

    # Team B Card
    draw.rounded_rectangle([610 + offset_b, 360, 980 + offset_b, 620], radius=24, fill=(17, 24, 39), outline=(55, 65, 81), width=3)
    draw.ellipse([745 + offset_b, 400, 845 + offset_b, 500], fill=(30, 41, 59))
    draw.text((795 + offset_b, 450), team_b[:3].upper(), font=get_font(36, bold=True), fill=(245, 158, 11), anchor="mm")
    draw.text((795 + offset_b, 550), team_b, font=get_font(30, bold=True), fill=(255, 255, 255), anchor="mm")

    # Deadline Banner
    deadline_txt = f"DEADLINE: {req.deadline or 'Match Start'}"
    draw.rounded_rectangle([140, 720, 940, 840], radius=20, fill=(220, 38, 38))
    draw.text((W // 2, 780), deadline_txt, font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")

    # CTA Bottom
    draw.text((W // 2, 940), "Select your Playing XI now at indusgamers.online", font=get_font(28, bold=True), fill=(16, 185, 129), anchor="mm")
    draw.text((W // 2, 985), "Free Private Leagues • Live Leaderboards", font=get_font(22), fill=(156, 163, 175), anchor="mm")

    return img


def draw_podium_frame(req: VideoRequest, frame_idx: int, total_frames: int) -> Image.Image:
    W, H = 1080, 1080
    t = frame_idx / total_frames

    img = Image.new("RGB", (W, H), (10, 15, 30))
    draw = ImageDraw.Draw(img)

    # Ambient golden glow
    glow_alpha = int(45 + 25 * math.sin(t * math.pi * 3))
    draw.ellipse([340, 200, 740, 600], fill=(245, 158, 11, glow_alpha))

    # Header
    draw.text((W // 2, 70), "INDUS GAMERS", font=get_font(34, bold=True), fill=(16, 185, 129), anchor="mm")
    draw.text((W // 2, 120), "MATCH COMPLETED • TOP FANTASY MANAGERS", font=get_font(24), fill=(156, 163, 175), anchor="mm")

    # Series / Result
    if req.series:
        s_txt = req.series if len(req.series) <= 44 else req.series[:42] + "..."
        draw.text((W // 2, 180), s_txt, font=get_font(26, bold=True), fill=(255, 255, 255), anchor="mm")
    if req.result:
        draw.text((W // 2, 220), req.result[:55], font=get_font(22), fill=(245, 158, 11), anchor="mm")

    # Rising Columns Animation (ease-out across first 1.5s)
    rise_progress = min(1.0, frame_idx / 45.0)
    ease = 1.0 - math.pow(1.0 - rise_progress, 3)

    winners = req.winners or []
    w1 = winners[0] if len(winners) > 0 else Winner(name="Champion", points=0, rank=1)
    w2 = winners[1] if len(winners) > 1 else Winner(name="Runner Up", points=0, rank=2)
    w3 = winners[2] if len(winners) > 2 else Winner(name="3rd Place", points=0, rank=3)

    # Target Heights
    h1_target, h2_target, h3_target = 360, 260, 200
    base_y = 860

    h1 = int(h1_target * ease)
    h2 = int(h2_target * ease)
    h3 = int(h3_target * ease)

    # 2nd Place (Left)
    draw.rounded_rectangle([140, base_y - h2, 380, base_y], radius=16, fill=(100, 116, 139))
    draw.text((260, base_y - h2 + 60), "2nd", font=get_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((260, base_y - h2 - 70), w2.name[:16], font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((260, base_y - h2 - 30), f"{w2.points:.0f} pts", font=get_font(26), fill=(203, 213, 225), anchor="mm")

    # 1st Place (Center - Gold)
    draw.rounded_rectangle([420, base_y - h1, 660, base_y], radius=16, fill=(245, 158, 11))
    draw.text((540, base_y - h1 + 60), "1st", font=get_font(52, bold=True), fill=(0, 0, 0), anchor="mm")
    # Gold Crown / Badge
    draw.text((540, base_y - h1 - 85), "★ WINNER ★", font=get_font(22, bold=True), fill=(245, 158, 11), anchor="mm")
    draw.text((540, base_y - h1 - 45), w1.name[:16], font=get_font(32, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((540, base_y - h1 - 5), f"{w1.points:.0f} pts", font=get_font(30, bold=True), fill=(245, 158, 11), anchor="mm")

    # 3rd Place (Right)
    draw.rounded_rectangle([700, base_y - h3, 940, base_y], radius=16, fill=(180, 83, 9))
    draw.text((820, base_y - h3 + 50), "3rd", font=get_font(40, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((820, base_y - h3 - 70), w3.name[:16], font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((820, base_y - h3 - 30), f"{w3.points:.0f} pts", font=get_font(26), fill=(253, 186, 116), anchor="mm")

    # Bottom Footer
    draw.text((W // 2, 940), "Check full leaderboard at indusgamers.online", font=get_font(26, bold=True), fill=(16, 185, 129), anchor="mm")

    return img


# --- Video Rendering with FFmpeg ---

import tempfile

@app.post("/generate-video")
def generate_video(req: VideoRequest):
    fps = 30
    duration = 5
    total_frames = fps * duration

    # Use a temporary file so FFmpeg can apply +faststart cleanly
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        out_path = tf.name

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ffmpeg: {e}")

    try:
        for i in range(total_frames):
            if req.type == "match_reminder":
                frame = draw_reminder_frame(req, i, total_frames)
            else:
                frame = draw_podium_frame(req, i, total_frames)

            buf = BytesIO()
            frame.save(buf, format="PNG")
            proc.stdin.write(buf.getvalue())
            buf.close()

        stdout_data, stderr_data = proc.communicate(timeout=60)
    except Exception as e:
        proc.kill()
        try:
            os.remove(out_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Encoding error: {e}")

    if proc.returncode != 0:
        try:
            os.remove(out_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"FFmpeg failed: {stderr_data.decode('utf-8', errors='ignore')[-300:]}")

    with open(out_path, "rb") as f:
        video_bytes = f.read()

    try:
        os.remove(out_path)
    except Exception:
        pass

    return Response(content=video_bytes, media_type="video/mp4")
