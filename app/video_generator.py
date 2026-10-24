import os
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
FPS = 30
DURATION_SEC = 5
TOTAL_FRAMES = FPS * DURATION_SEC  # 150 frames

def get_font(size: int, bold: bool = False):
    font_names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in font_names:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, series: str):
    # Brand Top
    font_brand = get_font(32, bold=True)
    draw.text((W // 2, 80), "INDUS GAMERS", fill=(0, 240, 255), font=font_brand, anchor="mm")
    
    font_sub = get_font(20)
    draw.text((W // 2, 120), "FANTASY CRICKET • indusgamers.online", fill=(180, 190, 210), font=font_sub, anchor="mm")
    
    # Series badge
    font_series = get_font(22, bold=True)
    draw.rectangle([60, 160, W - 60, 210], fill=(24, 30, 48), outline=(0, 200, 255), width=2)
    draw.text((W // 2, 185), (series or "CRICKET SERIES").upper()[:40], fill=(255, 255, 255), font=font_series, anchor="mm")
    
    # Title & Subtitle
    font_title = get_font(34, bold=True)
    draw.text((W // 2, 260), title[:35], fill=(255, 220, 80), font=font_title, anchor="mm")
    
    font_subt = get_font(24)
    draw.text((W // 2, 305), subtitle[:45], fill=(200, 220, 255), font=font_subt, anchor="mm")

def draw_footer(draw: ImageDraw.ImageDraw):
    font_cta = get_font(24, bold=True)
    draw.rectangle([80, H - 110, W - 80, H - 50], fill=(0, 200, 255))
    draw.text((W // 2, H - 80), "PLAY NOW • www.indusgamers.online", fill=(10, 14, 26), font=font_cta, anchor="mm")

# --- TEMPLATE 1: MATCH REMINDER (DEADLINE COUNTDOWN) ---
def render_reminder_frame(frame_idx: int, data: Dict[str, Any]) -> Image.Image:
    img = Image.new("RGB", (W, H), color=(12, 16, 28))
    draw = ImageDraw.Draw(img)
    
    # Background subtle grid / gradient effect
    draw.rectangle([0, 0, W, H], fill=(12, 16, 28))
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(18, 24, 42), width=1)
        
    draw_header(draw, data.get("title", "MATCH REMINDER"), data.get("subtitle", "Entry Deadline Closing Soon"), data.get("series", ""))
    
    # Match Clash Banner: Team A vs Team B
    team_a = data.get("team_a", "TEAM A").upper()
    team_b = data.get("team_b", "TEAM B").upper()
    
    # Team Clash Boxes
    draw.rectangle([60, 370, 320, 510], fill=(22, 32, 54), outline=(0, 240, 255), width=2)
    font_team = get_font(30, bold=True)
    draw.text((190, 440), team_a[:12], fill=(255, 255, 255), font=font_team, anchor="mm")
    
    font_vs = get_font(36, bold=True)
    draw.text((W // 2, 440), "VS", fill=(255, 70, 85), font=font_vs, anchor="mm")
    
    draw.rectangle([400, 370, 660, 510], fill=(22, 32, 54), outline=(255, 70, 85), width=2)
    draw.text((530, 440), team_b[:12], fill=(255, 255, 255), font=font_team, anchor="mm")
    
    # Venue Info
    venue = data.get("venue", "Stadium")
    font_venue = get_font(20)
    draw.text((W // 2, 560), f"📍 {venue}"[:45], fill=(180, 200, 220), font=font_venue, anchor="mm")
    
    # Animated Deadline Box
    deadline = data.get("deadline", "Shortly")
    draw.rectangle([50, 620, W - 50, 800], fill=(26, 20, 36), outline=(255, 180, 0), width=3)
    
    font_warn = get_font(24, bold=True)
    # Pulsing warning color
    pulse = abs((frame_idx % 30) - 15) / 15.0
    warn_color = (255, int(150 + 105 * pulse), 0)
    draw.text((W // 2, 670), "⚠️ TEAM SUBMISSION DEADLINE", fill=warn_color, font=font_warn, anchor="mm")
    
    font_dead = get_font(32, bold=True)
    draw.text((W // 2, 730), deadline, fill=(255, 255, 255), font=font_dead, anchor="mm")
    
    # Animated Progress Bar (fills up across 5 seconds)
    bar_progress = min(1.0, frame_idx / float(TOTAL_FRAMES))
    bar_width = int((W - 140) * bar_progress)
    draw.rectangle([70, 840, W - 70, 860], fill=(24, 30, 48), outline=(60, 70, 95), width=1)
    if bar_width > 0:
        draw.rectangle([70, 840, 70 + bar_width, 860], fill=(0, 255, 136))
    
    font_bar = get_font(18)
    draw.text((W // 2, 890), "LOCK IN YOUR PLAYING XI BEFORE FIRST BALL", fill=(170, 185, 210), font=font_bar, anchor="mm")
    
    draw_footer(draw)
    return img

# --- TEMPLATE 2: MATCH PODIUM (STANDINGS & WINNERS) ---
def render_podium_frame(frame_idx: int, data: Dict[str, Any]) -> Image.Image:
    img = Image.new("RGB", (W, H), color=(10, 14, 26))
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, data.get("title", "MATCH STANDINGS"), data.get("subtitle", "Fantasy League Winners"), data.get("series", ""))
    
    # Result banner
    result = data.get("result", "")
    if result:
        font_res = get_font(20, bold=True)
        draw.text((W // 2, 360), result[:50], fill=(160, 255, 180), font=font_res, anchor="mm")
        
    winners = data.get("winners", [])
    w1 = winners[0] if len(winners) > 0 else {"name": "Manager 1", "points": 0}
    w2 = winners[1] if len(winners) > 1 else {"name": "Manager 2", "points": 0}
    w3 = winners[2] if len(winners) > 2 else {"name": "Manager 3", "points": 0}
    
    # Animation: Columns rise from bottom y=1050 up to their target height during frames 0..60 (first 2.0s)
    anim_progress = min(1.0, frame_idx / 60.0)
    # Ease-out cubic
    ease = 1.0 - pow(1.0 - anim_progress, 3)
    
    base_y = 1050
    # Target tops of the 3 podium blocks
    target_top_1st = 620   # Tallest center
    target_top_2nd = 720   # Left
    target_top_3rd = 790   # Right
    
    current_top_1st = int(base_y - (base_y - target_top_1st) * ease)
    current_top_2nd = int(base_y - (base_y - target_top_2nd) * ease)
    current_top_3rd = int(base_y - (base_y - target_top_3rd) * ease)
    
    # Draw 2nd Place (Left)
    draw.rectangle([50, current_top_2nd, 230, base_y], fill=(35, 45, 68), outline=(192, 192, 210), width=3)
    # Draw 1st Place (Center - Golden/Cyan)
    draw.rectangle([250, current_top_1st, 470, base_y], fill=(22, 55, 80), outline=(0, 240, 255), width=4)
    # Draw 3rd Place (Right - Bronze)
    draw.rectangle([490, current_top_3rd, 670, base_y], fill=(42, 35, 30), outline=(205, 127, 50), width=3)
    
    # Podium Numbers inside columns
    font_rank = get_font(52, bold=True)
    draw.text((140, current_top_2nd + 70), "2", fill=(192, 192, 210), font=font_rank, anchor="mm")
    draw.text((360, current_top_1st + 75), "1", fill=(0, 240, 255), font=font_rank, anchor="mm")
    draw.text((580, current_top_3rd + 65), "3", fill=(205, 127, 50), font=font_rank, anchor="mm")
    
    # Labels and Winner Info (Shown above each column as it locks in)
    font_bold = get_font(22, bold=True)
    font_pts = get_font(20)
    font_champ = get_font(24, bold=True)
    
    # 1st Champion
    draw.text((360, current_top_1st - 110), "CHAMPION", fill=(255, 215, 0), font=font_champ, anchor="mm")
    draw.text((360, current_top_1st - 70), str(w1.get("name", ""))[:14], fill=(255, 255, 255), font=font_bold, anchor="mm")
    draw.text((360, current_top_1st - 35), f"{w1.get('points', 0)} PTS", fill=(0, 240, 255), font=font_pts, anchor="mm")
    
    # 2nd Place
    draw.text((140, current_top_2nd - 60), str(w2.get("name", ""))[:13], fill=(255, 255, 255), font=font_bold, anchor="mm")
    draw.text((140, current_top_2nd - 30), f"{w2.get('points', 0)} PTS", fill=(200, 210, 230), font=font_pts, anchor="mm")
    
    # 3rd Place
    draw.text((580, current_top_3rd - 60), str(w3.get("name", ""))[:13], fill=(255, 255, 255), font=font_bold, anchor="mm")
    draw.text((580, current_top_3rd - 30), f"{w3.get('points', 0)} PTS", fill=(225, 170, 120), font=font_pts, anchor="mm")
    
    draw_footer(draw)
    return img

def generate_mp4_bytes(payload: Dict[str, Any]) -> bytes:
    video_type = payload.get("type", "match_podium")
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_out:
        out_path = tmp_out.name

    # FFmpeg command piping raw video frames directly
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",  # Read from stdin pipe
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-t", str(DURATION_SEC),
        out_path
    ]
    
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    try:
        for f in range(TOTAL_FRAMES):
            if video_type == "match_reminder":
                frame_img = render_reminder_frame(f, payload)
            else:
                frame_img = render_podium_frame(f, payload)
            proc.stdin.write(frame_img.tobytes())
            
        proc.stdin.close()
        proc.wait(timeout=30)
    except Exception as e:
        proc.kill()
        if os.path.exists(out_path):
            os.remove(out_path)
        raise e

    with open(out_path, "rb") as f:
        data = f.read()

    os.remove(out_path)
    return data
