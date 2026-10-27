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

def get_team_abbr(team_name: str) -> str:
    """Returns 2-letter abbreviation for 2-word teams (S.L, S.A, N.Z) or 3 letters for 1-word teams (PAK, IND, AUS)."""
    if not team_name:
        return "T1"
    words = team_name.strip().split()
    if len(words) >= 2:
        return f"{words[0][0].upper()}.{words[1][0].upper()}"
    return team_name[:3].upper()


# --- Draw Frame Functions (1080x1080) ---

def draw_reminder_frame(req: VideoRequest, frame_idx: int, total_frames: int) -> Image.Image:
    W, H = 1080, 1080
    t = frame_idx / total_frames

    # High-contrast stadium dark gradient background
    img = Image.new("RGB", (W, H), (8, 14, 28))
    draw = ImageDraw.Draw(img)

    for y in range(0, H, 15):
        factor = y / H
        r = int(8 + factor * 10)
        g = int(14 + factor * 16)
        b = int(28 + factor * 30)
        draw.rectangle([0, y, W, y + 15], fill=(r, g, b))

    # Top & bottom glowing sports borders
    draw.rectangle([0, 0, W, 8], fill=(16, 185, 129))  # Emerald top border
    draw.rectangle([0, H - 8, W, H], fill=(245, 158, 11))  # Gold bottom border

    # Ambient stadium light beam accents
    draw.polygon([(0, 0), (320, 0), (160, 450), (0, 300)], fill=(15, 32, 58))
    draw.polygon([(W, 0), (W - 320, 0), (W - 160, 450), (W, 300)], fill=(15, 32, 58))

    # --- TOP BRAND HEADER ---
    draw.rounded_rectangle([320, 38, 760, 102], radius=32, fill=(15, 23, 42), outline=(52, 211, 153), width=3)
    draw.text((W // 2, 70), "INDUS GAMERS", font=get_font(36, bold=True), fill=(52, 211, 153), anchor="mm")
    draw.text((W // 2, 130), "FANTASY CRICKET • MATCH REMINDER", font=get_font(23, bold=True), fill=(241, 245, 249), anchor="mm")

    # --- SERIES & VENUE CARD ---
    series_txt = (req.series or "Upcoming Match").upper()
    if len(series_txt) > 42:
        series_txt = series_txt[:40] + "..."

    draw.rounded_rectangle([100, 168, 980, 275], radius=18, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    # Series badge
    draw.rounded_rectangle([125, 185, 245, 222], radius=8, fill=(245, 158, 11))
    draw.text((185, 203), "SERIES", font=get_font(18, bold=True), fill=(15, 23, 42), anchor="mm")
    draw.text((595, 203), series_txt, font=get_font(26, bold=True), fill=(255, 255, 255), anchor="mm")

        # --- VENUE CARD ---
    venue_txt = f"VENUE: {req.venue[:50]}" if req.venue else "VENUE: International Cricket Stadium"
    draw.rounded_rectangle([140, 175, 940, 248], radius=16, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    draw.text((W // 2, 211), venue_txt, font=get_font(22, bold=True), fill=(203, 213, 225), anchor="mm")



    # --- TEAM CLASH CARDS ---
    team_a = req.team_a or "Team A"
    team_b = req.team_b or "Team B"

    slide = min(1.0, frame_idx / 25.0) if total_frames > 0 else 1.0
    ease = 1.0 - math.pow(1.0 - slide, 3)
    offset_a = int((1.0 - ease) * -400)
    offset_b = int((1.0 - ease) * 400)

    # Team A Card (Emerald Accent)
    draw.rounded_rectangle([90 + offset_a, 320, 470 + offset_a, 630], radius=24, fill=(15, 23, 42), outline=(16, 185, 129), width=4)
    # Emblem Circle
    draw.ellipse([220 + offset_a, 355, 340 + offset_a, 475], fill=(6, 78, 59), outline=(52, 211, 153), width=3)
    draw.text((280 + offset_a, 415), get_team_abbr(team_a), font=get_font(38, bold=True), fill=(255, 255, 255), anchor="mm")
    # Name Plate
    draw.rounded_rectangle([110 + offset_a, 498, 450 + offset_a, 562], radius=12, fill=(24, 38, 66), outline=(52, 211, 153), width=1)
    draw.text((280 + offset_a, 530), team_a, font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((280 + offset_a, 595), "TEAM 1", font=get_font(20, bold=True), fill=(52, 211, 153), anchor="mm")

    # VS Badge (Pulsing Amber/Red)
    pulse = 1.0 + 0.10 * math.sin(t * math.pi * 8)
    radius_vs = int(48 * pulse)
    draw.ellipse([540 - radius_vs - 6, 475 - radius_vs - 6, 540 + radius_vs + 6, 475 + radius_vs + 6], fill=(220, 38, 38))
    draw.ellipse([540 - radius_vs, 475 - radius_vs, 540 + radius_vs, 475 + radius_vs], fill=(245, 158, 11), outline=(255, 255, 255), width=3)
    draw.text((540, 475), "VS", font=get_font(34, bold=True), fill=(15, 23, 42), anchor="mm")

    # Team B Card (Gold Accent)
    draw.rounded_rectangle([610 + offset_b, 320, 990 + offset_b, 630], radius=24, fill=(15, 23, 42), outline=(245, 158, 11), width=4)
    # Emblem Circle
    draw.ellipse([740 + offset_b, 355, 860 + offset_b, 475], fill=(120, 53, 15), outline=(251, 191, 36), width=3)
    draw.text((800 + offset_b, 415), get_team_abbr(team_b), font=get_font(38, bold=True), fill=(255, 255, 255), anchor="mm")
    # Name Plate
    draw.rounded_rectangle([630 + offset_b, 498, 970 + offset_b, 562], radius=12, fill=(24, 38, 66), outline=(245, 158, 11), width=1)
    draw.text((800 + offset_b, 530), team_b, font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((800 + offset_b, 595), "TEAM 2", font=get_font(20, bold=True), fill=(251, 191, 36), anchor="mm")

    # --- DEADLINE BANNER ---
    deadline_val = req.deadline or "Match Start"
    draw.rounded_rectangle([90, 675, 990, 785], radius=22, fill=(185, 28, 28), outline=(248, 113, 113), width=3)
    draw.rounded_rectangle([115, 698, 265, 762], radius=12, fill=(127, 29, 29))
    draw.text((190, 730), "LOCKS AT", font=get_font(20, bold=True), fill=(254, 202, 202), anchor="mm")
    draw.text((620, 730), f"DEADLINE: {deadline_val}", font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")

    # --- CTA FOOTER ---
    draw.rounded_rectangle([90, 835, 990, 950], radius=24, fill=(15, 23, 42), outline=(16, 185, 129), width=2)
    draw.text((W // 2, 873), "Create Your Playing XI & Win!", font=get_font(30, bold=True), fill=(52, 211, 153), anchor="mm")
    draw.text((W // 2, 915), "indusgamers.online • Free Leagues & Live Rankings", font=get_font(23, bold=True), fill=(241, 245, 249), anchor="mm")

    return img
    

def draw_podium_frame(req: VideoRequest, frame_idx: int, total_frames: int) -> Image.Image:
    W, H = 1080, 1080
    t = frame_idx / total_frames

    # Background gradient with deep midnight sports feel
    img = Image.new("RGB", (W, H), (8, 14, 28))
    draw = ImageDraw.Draw(img)

    for y in range(0, H, 15):
        factor = y / H
        r = int(8 + factor * 10)
        g = int(14 + factor * 16)
        b = int(28 + factor * 30)
        draw.rectangle([0, y, W, y + 15], fill=(r, g, b))

    # Top & bottom gold/emerald borders
    draw.rectangle([0, 0, W, 8], fill=(245, 158, 11))
    draw.rectangle([0, H - 8, W, H], fill=(16, 185, 129))

    # Ambient golden spotlight polygon
    draw.polygon([(W // 2 - 250, 0), (W // 2 + 250, 0), (W // 2 + 380, 500), (W // 2 - 380, 500)], fill=(26, 33, 50))

    # --- TOP BRAND HEADER ---
    draw.rounded_rectangle([320, 38, 760, 102], radius=32, fill=(15, 23, 42), outline=(245, 158, 11), width=3)
    draw.text((W // 2, 70), "INDUS GAMERS", font=get_font(36, bold=True), fill=(251, 191, 36), anchor="mm")
    draw.text((W // 2, 130), "MATCH COMPLETED • TOP FANTASY MANAGERS", font=get_font(23, bold=True), fill=(241, 245, 249), anchor="mm")

    # --- RESULT CARD ---
    res_txt = (req.result or "Match Completed").upper()
    if len(res_txt) > 55:
        res_txt = res_txt[:52] + "..."
    draw.rounded_rectangle([140, 175, 940, 248], radius=16, fill=(15, 23, 42), outline=(16, 185, 129), width=2)
    draw.text((W // 2, 211), res_txt, font=get_font(27, bold=True), fill=(52, 211, 153), anchor="mm")


    # Rising Columns Animation
    rise_progress = min(1.0, frame_idx / 45.0) if total_frames > 0 else 1.0
    ease = 1.0 - math.pow(1.0 - rise_progress, 3)

    winners = req.winners or []
    w1 = winners[0] if len(winners) > 0 else Winner(name="Champion", points=0, rank=1)
    w2 = winners[1] if len(winners) > 1 else Winner(name="Runner Up", points=0, rank=2)
    w3 = winners[2] if len(winners) > 2 else Winner(name="3rd Place", points=0, rank=3)

    base_y = 860
    h1_target, h2_target, h3_target = 370, 270, 210
    h1 = int(h1_target * ease)
    h2 = int(h2_target * ease)
    h3 = int(h3_target * ease)

    # --- 2ND PLACE (SILVER / LEFT) ---
    badge2_y = base_y - h2
    draw.rounded_rectangle([100, badge2_y - 110, 360, badge2_y - 15], radius=14, fill=(15, 23, 42), outline=(203, 213, 225), width=2)
    draw.text((230, badge2_y - 82), w2.name[:16], font=get_font(24, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((230, badge2_y - 45), f"{w2.points:.1f} PTS", font=get_font(24, bold=True), fill=(147, 197, 253), anchor="mm")

    # Pillar
    draw.rounded_rectangle([110, base_y - h2, 350, base_y], radius=16, fill=(148, 163, 184), outline=(226, 232, 240), width=3)
    draw.ellipse([190, base_y - h2 + 25, 270, base_y - h2 + 105], fill=(226, 232, 240))
    draw.text((230, base_y - h2 + 65), "2nd", font=get_font(36, bold=True), fill=(15, 23, 42), anchor="mm")

    # --- 1ST PLACE (GOLD / CENTER) ---
    badge1_y = base_y - h1
    draw.rounded_rectangle([390, badge1_y - 130, 690, badge1_y - 15], radius=16, fill=(15, 23, 42), outline=(245, 158, 11), width=3)
    draw.text((540, badge1_y - 104), "★ CHAMPION ★", font=get_font(20, bold=True), fill=(251, 191, 36), anchor="mm")
    draw.text((540, badge1_y - 70), w1.name[:16], font=get_font(30, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((540, badge1_y - 32), f"{w1.points:.1f} PTS", font=get_font(26, bold=True), fill=(253, 224, 71), anchor="mm")

    # Pillar
    draw.rounded_rectangle([400, base_y - h1, 680, base_y], radius=18, fill=(245, 158, 11), outline=(254, 240, 138), width=4)
    draw.ellipse([490, base_y - h1 + 30, 590, base_y - h1 + 130], fill=(254, 240, 138))
    draw.text((540, base_y - h1 + 80), "1st", font=get_font(46, bold=True), fill=(15, 23, 42), anchor="mm")

    # --- 3RD PLACE (BRONZE / RIGHT) ---
    badge3_y = base_y - h3
    draw.rounded_rectangle([720, badge3_y - 110, 980, badge3_y - 15], radius=14, fill=(15, 23, 42), outline=(217, 119, 6), width=2)
    draw.text((850, badge3_y - 82), w3.name[:16], font=get_font(24, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((850, badge3_y - 45), f"{w3.points:.1f} PTS", font=get_font(24, bold=True), fill=(253, 186, 116), anchor="mm")

    # Pillar
    draw.rounded_rectangle([730, base_y - h3, 970, base_y], radius=16, fill=(217, 119, 6), outline=(251, 191, 36), width=3)
    draw.ellipse([810, base_y - h3 + 20, 890, base_y - h3 + 100], fill=(254, 215, 170))
    draw.text((850, base_y - h3 + 60), "3rd", font=get_font(36, bold=True), fill=(67, 20, 7), anchor="mm")

    # --- FOOTER ---
    draw.rounded_rectangle([90, 890, 990, 965], radius=20, fill=(15, 23, 42), outline=(16, 185, 129), width=2)
    draw.text((W // 2, 928), "Check Full Leaderboard at indusgamers.online", font=get_font(26, bold=True), fill=(52, 211, 153), anchor="mm")

    return img

# --- Video Rendering with FFmpeg ---

import tempfile

@app.post("/generate-video")
async def generate_video(req: VideoRequest):
    import io, tempfile, os, subprocess
    out_path = None
    proc = None
    try:
        total_frames = 150  # 5 seconds @ 30fps

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            out_path = tf.name

        # Synthesize audio dynamically
        if req.type == "match_reminder":
            # Pulsing bass thump + countdown alert tone
            audio_filter = (
                "sine=f=110:d=5[bass];"
                "sine=f=880:d=5[beep];"
                "[bass]tremolo=f=4:d=0.8,volume=1.2[b1];"
                "[beep]tremolo=f=2:d=0.9,volume=0.25[b2];"
                "[b1][b2]amix=inputs=2:duration=first,afade=t=out:st=4.3:d=0.7[aout]"
            )
        else:
            # Match Podium: Victory chord + cheer wash
            audio_filter = (
                "sine=f=261.63:d=5[c];"
                "sine=f=329.63:d=5[e];"
                "sine=f=392.00:d=5[g];"
                "sine=f=523.25:d=5[c2];"
                "anoisesrc=d=5:c=white:r=44100[crowd];"
                "[crowd]lowpass=f=1200,volume=0.3,afade=t=in:st=0:d=1[cheer];"
                "[c][e][g][c2]amix=inputs=4:duration=first,volume=0.8[chord];"
                "[chord][cheer]amix=inputs=2:duration=first,afade=t=out:st=4.2:d=0.8[aout]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-r", "30",
            "-i", "-",
            "-filter_complex", audio_filter,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-preset", "fast",
            "-movflags", "+faststart",
            "-t", "5",
            out_path,
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for frame_idx in range(total_frames):
            if req.type == "match_reminder":
                img = draw_reminder_frame(req, frame_idx, total_frames)
            else:
                img = draw_podium_frame(req, frame_idx, total_frames)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            proc.stdin.write(buf.getvalue())

        proc.stdin.close()
        proc.wait(timeout=120)

        if proc.returncode != 0:
            err = proc.stderr.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=500, detail=f"FFmpeg failed: {err[-500:]}")

        with open(out_path, "rb") as f:
            video_bytes = f.read()

        return Response(content=video_bytes, media_type="video/mp4")

    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        raise HTTPException(status_code=504, detail="FFmpeg rendering timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if out_path and os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
