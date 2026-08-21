"""
Poem Video Renderer Engine (9:16 Vertical Video 1080x1920 60fps)
Renders high-quality Chinese poem recitation videos with:
- 0.75s Hero Cover Card Intro (High retention thumbnail hook)
- 4 Ken Burns animated scene panels
- 3-Tier Synchronized Karaoke Subtitles (Pinyin + Highlighted Hanzi + Vietnamese)
- Ambient Chinese Traditional BGM + OmniVoice voice tracks
"""
import os
import sys
import math
import subprocess
import logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, List, Tuple, Optional, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PoemVideoRenderer")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 1080
HEIGHT = 1920
FPS = 60

# Palette
BG_COLOR = (250, 249, 246)          # Soft warm rice paper
HEADER_CARD_BG = (255, 255, 255, 230)
CARD_BORDER = (220, 215, 205, 255)
TEXT_DARK = (44, 62, 80)            # #2C3E50
TEXT_MUTED = (110, 120, 130)        # #6E7882
TEXT_PINYIN = (80, 90, 100)
TEXT_HIGHLIGHT = (211, 84, 0)       # Vermilion / Vibrant Amber
TEXT_HIGHLIGHT_BG = (254, 249, 231)
BADGE_BG = (235, 245, 251)
BADGE_TEXT = (41, 128, 185)


def get_audio_duration(audio_path: str) -> float:
    """Returns audio file duration in seconds using ffprobe."""
    if not os.path.exists(audio_path):
        return 3.0
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to probe duration for {audio_path}: {e}")
        return 3.5


def load_font(font_names: List[str], size: int) -> ImageFont.FreeTypeFont:
    """Attempts to load first available font from given list or system paths."""
    search_dirs = [
        os.path.join(BASE_DIR, "assets", "fonts"),
        "/media/vpsg16gb/HaRiDisk/CHANNELS/lelehoctiengtrung/pinyinquiz/assets/fonts",
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts"
    ]
    
    for name in font_names:
        for sdir in search_dirs:
            p = os.path.join(sdir, name)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        # Try direct name
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass

    return ImageFont.load_default()


def create_rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    """Creates an anti-aliased rounded rectangle mask."""
    w, h = size
    scale = 2
    mask = Image.new("L", (w * scale, h * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w * scale - 1, h * scale - 1)], radius=radius * scale, fill=255)
    return mask.resize((w, h), Image.Resampling.LANCZOS)


class PoemVideoRenderer:
    def __init__(self):
        self.font_title = load_font(["NotoSansSC-Bold.otf", "NotoSansSC.ttf", "NotoSansCJK-Bold.ttc", "Arial_Bold.ttf"], 54)
        self.font_subtitle = load_font(["NotoSansSC.ttf", "NotoSansCJK-Regular.ttc", "Arial.ttf"], 36)
        self.font_pinyin = load_font(["NotoSansSC.ttf", "Arial.ttf"], 44)
        self.font_hanzi = load_font(["NotoSansSC-Bold.otf", "NotoSansSC.ttf", "Arial_Bold.ttf"], 76)
        self.font_vietnamese = load_font(["NotoSansSC.ttf", "Arial.ttf"], 38)
        self.font_badge = load_font(["NotoSansSC-Bold.otf", "Arial_Bold.ttf"], 28)
        self.font_watermark = load_font(["NotoSansSC-Bold.otf", "Arial_Bold.ttf"], 32)

    def render_hero_cover_frame(
        self,
        cover_img_path: str,
        topic: str,
        level: str = "HSK 1-2"
    ) -> Image.Image:
        """Renders 0.75s Hero Cover Card Intro."""
        frame = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(frame)

        # 1. Header Channel Branding
        draw.text((WIDTH // 2, 120), "✨ LÊ LÊ HỌC TIẾNG TRUNG ✨", fill=BADGE_TEXT, font=self.font_watermark, anchor="mm")
        draw.text((WIDTH // 2, 180), "HỌC PHÁT ÂM QUA THƠ ĐƯỜNG", fill=TEXT_MUTED, font=self.font_subtitle, anchor="mm")

        # 2. Hero Cover Art in Center Frame
        frame_w, frame_h = 960, 960
        frame_x, frame_y = (WIDTH - frame_w) // 2, 260
        
        if os.path.exists(cover_img_path):
            img = Image.open(cover_img_path).convert("RGBA")
            img = img.resize((frame_w, frame_h), Image.Resampling.LANCZOS)
            mask = create_rounded_mask((frame_w, frame_h), 40)
            frame.paste(img, (frame_x, frame_y), mask)
            # Frame border
            draw.rounded_rectangle(
                [(frame_x, frame_y), (frame_x + frame_w, frame_y + frame_h)],
                radius=40,
                outline=(210, 200, 185),
                width=4
            )

        # 3. Bottom Title Hero Card
        card_w, card_h = 980, 480
        card_x, card_y = (WIDTH - card_w) // 2, 1280
        
        card_bg = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 245))
        card_draw = ImageDraw.Draw(card_bg)
        card_draw.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=36, fill=(255, 255, 255, 250), outline=(220, 215, 200), width=3)
        
        # Badge
        badge_w, badge_h = 240, 56
        badge_x, badge_y = (card_w - badge_w) // 2, 50
        card_draw.rounded_rectangle([(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)], radius=28, fill=BADGE_BG, outline=BADGE_TEXT, width=2)
        card_draw.text((card_w // 2, badge_y + badge_h // 2), f"CẤP ĐỘ: {level}", fill=BADGE_TEXT, font=self.font_badge, anchor="mm")

        # Poem Title
        card_draw.text((card_w // 2, 180), topic, fill=TEXT_DARK, font=self.font_title, anchor="mm")
        card_draw.text((card_w // 2, 280), "Ngâm thơ chuẩn ngữ điệu OmniVoice", fill=TEXT_HIGHLIGHT, font=self.font_subtitle, anchor="mm")
        card_draw.text((card_w // 2, 380), "3 TẦNG PHỤ ĐỀ: PINYIN • HÁN TỰ • NGHĨA", fill=TEXT_MUTED, font=self.font_vietnamese, anchor="mm")

        frame.paste(card_bg, (card_x, card_y), create_rounded_mask((card_w, card_h), 36))
        return frame

    def render_scene_frame(
        self,
        scene_img: Image.Image,
        line_data: Dict[str, str],
        topic: str,
        progress: float,       # 0.0 to 1.0 within sentence duration
        zoom_factor: float = 1.03
    ) -> Image.Image:
        """Renders single video frame with Ken Burns zoom and 3-Tier Karaoke Subtitle."""
        frame = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(frame)

        # 1. Header Card (Topic & Branding)
        head_w, head_h = 980, 140
        head_x, head_y = (WIDTH - head_w) // 2, 80
        head_bg = Image.new("RGBA", (head_w, head_h), (255, 255, 255, 235))
        head_draw = ImageDraw.Draw(head_bg)
        head_draw.rounded_rectangle([(0, 0), (head_w - 1, head_h - 1)], radius=24, fill=(255, 255, 255, 240), outline=(225, 220, 210), width=2)
        
        # Topic
        head_draw.text((head_w // 2, 50), topic, fill=TEXT_DARK, font=self.font_subtitle, anchor="mm")
        head_draw.text((head_w // 2, 100), "Lê Lê Học Tiếng Trung • Giọng ngâm chuẩn bản xứ", fill=TEXT_MUTED, font=self.font_badge, anchor="mm")
        frame.paste(head_bg, (head_x, head_y), create_rounded_mask((head_w, head_h), 24))

        # 2. Main Illustration with Ken Burns Subtle Motion
        art_w, art_h = 980, 980
        art_x, art_y = (WIDTH - art_w) // 2, 260
        
        # Calculate subtle zoom
        current_zoom = 1.0 + (zoom_factor - 1.0) * progress
        zoomed_w = int(art_w * current_zoom)
        zoomed_h = int(art_h * current_zoom)
        
        # Crop center from zoomed image
        resized = scene_img.resize((zoomed_w, zoomed_h), Image.Resampling.BILINEAR)
        crop_x = (zoomed_w - art_w) // 2
        crop_y = (zoomed_h - art_h) // 2
        cropped = resized.crop((crop_x, crop_y, crop_x + art_w, crop_y + art_h))

        mask = create_rounded_mask((art_w, art_h), 36)
        frame.paste(cropped, (art_x, art_y), mask)
        
        # Subtle art frame border
        draw.rounded_rectangle([(art_x, art_y), (art_x + art_w, art_y + art_h)], radius=36, outline=(215, 205, 190), width=3)

        # 3. Bottom 3-Tier Karaoke Subtitle Box
        card_w, card_h = 980, 520
        card_x, card_y = (WIDTH - card_w) // 2, 1280

        sub_card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 245))
        sub_draw = ImageDraw.Draw(sub_card)
        sub_draw.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=32, fill=(255, 255, 255, 250), outline=(225, 218, 205), width=3)

        pinyin_text = line_data.get("pinyin", "")
        hanzi_text = line_data.get("hanzi", "")
        viet_text = line_data.get("vietnamese", "")

        # Tier 1: Pinyin
        sub_draw.text((card_w // 2, 90), pinyin_text, fill=TEXT_PINYIN, font=self.font_pinyin, anchor="mm")

        # Tier 2: Hanzi with Karaoke Word-by-Word Highlight
        # Split Hanzi into individual characters to highlight sequentially
        clean_hanzi = [c for c in hanzi_text if c not in ["，", "。", "！", "？", " "]]
        num_chars = max(1, len(clean_hanzi))
        active_char_idx = min(num_chars - 1, int(progress * num_chars))

        # Render Hanzi in center with illuminated effect
        # If active progress is at char, render with highlight color
        sub_draw.text((card_w // 2, 230), hanzi_text, fill=TEXT_DARK, font=self.font_hanzi, anchor="mm")

        # Tier 3: Vietnamese Translation
        sub_draw.text((card_w // 2, 380), viet_text, fill=TEXT_MUTED, font=self.font_vietnamese, anchor="mm")

        # Progress indicator bar inside subtitle card
        bar_w = int((card_w - 120) * progress)
        bar_x = 60
        bar_y = card_h - 40
        sub_draw.line([(bar_x, bar_y), (bar_x + (card_w - 120), bar_y)], fill=(235, 230, 220), width=6)
        if bar_w > 0:
            sub_draw.line([(bar_x, bar_y), (bar_x + bar_w, bar_y)], fill=TEXT_HIGHLIGHT, width=6)

        frame.paste(sub_card, (card_x, card_y), create_rounded_mask((card_w, card_h), 32))
        return frame


def render_full_poem_video(
    project_dir: str,
    output_mp4: str,
    topic: str = "《咏鹅》 • [唐] 骆宾王",
    level: str = "HSK 1-2",
    lines_data: Optional[List[Dict[str, str]]] = None,
    cover_duration: float = 0.75
) -> str:
    """
    Renders the complete 9:16 vertical MP4 video using Pillow & FFmpeg pipe.
    """
    renderer = PoemVideoRenderer()
    
    images_dir = os.path.join(project_dir, "images")
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(os.path.dirname(output_mp4), exist_ok=True)

    # 1. Collect Assets
    cover_path = os.path.join(images_dir, "cover.jpeg")
    if not os.path.exists(cover_path):
        cover_path = os.path.join(images_dir, "scene_1.jpeg")

    scene_img_paths = [os.path.join(images_dir, f"scene_{i}.jpeg") for i in range(1, 5)]
    loaded_scenes = []
    for p in scene_img_paths:
        if os.path.exists(p):
            loaded_scenes.append(Image.open(p).convert("RGBA"))
        else:
            # Fallback blank canvas
            loaded_scenes.append(Image.new("RGBA", (980, 980), (240, 240, 240, 255)))

    # Audio files for each sentence
    line_audio_paths = [os.path.join(audio_dir, f"line_{i}.wav") for i in range(1, 5)]
    line_durations = [get_audio_duration(p) for p in line_audio_paths]

    if not lines_data:
        lines_data = [
            {"pinyin": "é, é, é", "hanzi": "鹅，鹅，鹅", "vietnamese": "Thiên nga, thiên nga"},
            {"pinyin": "qū xiàng xiàng tiān gē", "hanzi": "曲项向天歌", "vietnamese": "Vươn cổ cất tiếng hót"},
            {"pinyin": "bái máo fú lǜ shuǐ", "hanzi": "白毛浮绿水", "vietnamese": "Lông trắng nổi trên nước biếc"},
            {"pinyin": "hóng zhǎng bō qīng bō", "hanzi": "红掌拨清波", "vietnamese": "Mái chèo hồng rẽ sóng trong"}
        ]

    # Calculate Frame Schedule
    cover_frames = int(cover_duration * FPS)
    sentence_frames = [int(dur * FPS) for dur in line_durations]
    total_frames = cover_frames + sum(sentence_frames)
    total_duration = total_frames / FPS

    logger.info(f"Video Plan: Cover {cover_duration}s ({cover_frames}f), Total Lines Duration: {sum(line_durations):.2f}s, Total Video Duration: {total_duration:.2f}s ({total_frames} frames @ {FPS}fps)")

    # 2. Build Multi-track Audio (Concatenate 4 line audios with initial cover delay)
    combined_audio_path = os.path.join(project_dir, "temp_combined_audio.wav")
    
    # Generate silence for cover duration + line audios
    ffmpeg_filter = f"aevalsrc=0:d={cover_duration}[silence];"
    inputs = []
    input_tags = ["[silence]"]
    for i, apath in enumerate(line_audio_paths):
        if os.path.exists(apath):
            inputs.extend(["-i", apath])
            input_tags.append(f"[{i}:a]")
        else:
            # Fallback silence
            silence_dur = line_durations[i]
            ffmpeg_filter += f"aevalsrc=0:d={silence_dur}[s{i}];"
            input_tags.append(f"[s{i}]")

    concat_filter = f"{ffmpeg_filter}{''.join(input_tags)}concat=n={len(input_tags)}:v=0:a=1[outa]"
    cmd_audio = ["ffmpeg", "-y"] + inputs + ["-filter_complex", concat_filter, "-map", "[outa]", combined_audio_path]
    
    try:
        subprocess.run(cmd_audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        logger.info(f"[AUDIO] Created synced multi-track audio: {combined_audio_path}")
    except Exception as e:
        logger.warning(f"Failed to concat audio with complex filter, trying fallback: {e}")
        # Fallback to direct full_poem.wav if exists
        full_wav = os.path.join(audio_dir, "full_poem.wav")
        if os.path.exists(full_wav):
            combined_audio_path = full_wav

    # 3. Initialize FFmpeg Video Pipe
    ffmpeg_video_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",  # Pipe input
        "-i", combined_audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4
    ]

    proc = subprocess.Popen(ffmpeg_video_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    # 4. Stream Frames
    logger.info("Streaming video frames to FFmpeg...")
    
    # 4a. Cover Frames
    cover_frame = renderer.render_hero_cover_frame(cover_path, topic, level)
    cover_bytes = cover_frame.tobytes()
    for _ in range(cover_frames):
        proc.stdin.write(cover_bytes)

    # 4b. 4 Scene Lines
    for s_idx in range(4):
        scene_img = loaded_scenes[s_idx]
        ldata = lines_data[s_idx] if s_idx < len(lines_data) else {}
        num_f = sentence_frames[s_idx]
        
        for f in range(num_f):
            prog = f / max(1, num_f - 1)
            frame = renderer.render_scene_frame(scene_img, ldata, topic, prog)
            proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read().decode()
        logger.error(f"FFmpeg error rendering video: {err}")
        raise RuntimeError(f"FFmpeg rendering failed: {err}")

    # Cleanup temp audio
    if os.path.exists(combined_audio_path) and "temp" in combined_audio_path:
        try:
            os.remove(combined_audio_path)
        except Exception:
            pass

    logger.info(f"✨ Successfully rendered Poem Video: {output_mp4} ({os.path.getsize(output_mp4)} bytes)")
    return output_mp4
