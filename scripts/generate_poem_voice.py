"""
Script to synthesize poem voice on GitHub Actions using OmniVoice strictly
and upload all audio files directly into the poem's dedicated project folder on Google Drive.
"""
import os
import sys
import json
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeneratePoemVoice")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.poem_audio_generator import generate_poem_audio_omnivoice_strict
from src.drive_manager import DriveManager
from src.gsheet_manager import PoemGSheetManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID on Google Sheet (#)")
    parser.add_argument("--poem-id", type=str, default="", help="Poem Project ID (optional)")
    parser.add_argument("--folder-id", type=str, default="", help="Google Drive Project Folder ID (optional)")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    logger.info(f"Starting OmniVoice generation for Row #{row_id}...")

    # Reference audio sample
    voice_sample = os.path.join(BASE_DIR, "assets", "Vegetarian Wolf.wav")
    if not os.path.exists(voice_sample):
        raise FileNotFoundError(f"Missing required voice sample: {voice_sample}")

    tmp_audio_dir = os.path.join(BASE_DIR, "temp_audio")
    os.makedirs(tmp_audio_dir, exist_ok=True)

    # 1. Try reading dynamic data from Google Sheet
    gsheet_mgr = PoemGSheetManager()
    drive_mgr = DriveManager()
    
    poem_data = gsheet_mgr.get_poem_by_row_id(row_id)
    
    lines = []
    folder_id = args.folder_id or ""
    poem_id = args.poem_id or ""

    if poem_data:
        logger.info(f"[GSHEET] Fetched Poem: {poem_data.get('topic')} ({poem_data.get('level')})")
        lines = [l for l in poem_data.get("lines", []) if l.get("hanzi")]
        if not folder_id:
            folder_id = poem_data.get("folder_id", "")
        if not poem_id:
            poem_id = poem_data.get("poem_id", "")

    # Fallback to local default if sheet fetch unavailable
    if not lines:
        logger.warning(f"Using fallback database for Row #{row_id}")
        POEM_FALLBACK = {
            "2": [
                {"hanzi": "鹅，鹅，鹅", "pinyin": "é, é, é"},
                {"hanzi": "曲项向天歌", "pinyin": "qū xiàng xiàng tiān gē"},
                {"hanzi": "白毛浮绿水", "pinyin": "bái máo fú lǜ shuǐ"},
                {"hanzi": "红掌拨清波", "pinyin": "hóng zhǎng bō qīng bō"}
            ],
            "3": [
                {"hanzi": "远看山有色", "pinyin": "yuǎn kàn shān yǒu sè"},
                {"hanzi": "近听水无声", "pinyin": "jìn tīng shuǐ wú shēng"},
                {"hanzi": "春去花还在", "pinyin": "chūn qù huā hái zài"},
                {"hanzi": "人来鸟不惊", "pinyin": "rén lái niǎo bù jīng"}
            ]
        }
        lines = POEM_FALLBACK.get(row_id, POEM_FALLBACK["2"])
        if not folder_id and row_id == "2":
            folder_id = "1Fzyf9GHFg9fmWIQt4C-vvWKuF2Z5__gI"

    logger.info(f"Generating voice for {len(lines)} lines. Target Drive Folder ID: {folder_id or 'None'}")

    # 2. Synthesize & Upload individual sentence audios directly to GDrive project folder
    for idx, item in enumerate(lines, start=1):
        fname = f"line_{idx}.wav"
        out_line = os.path.join(tmp_audio_dir, fname)
        text = item.get("hanzi", "")
        logger.info(f"Synthesizing sentence {idx}: '{text}'...")
        generate_poem_audio_omnivoice_strict(text, out_line, voice_sample)

        if folder_id:
            drive_mgr.upload_file(out_line, fname, folder_id, mime_type="audio/wav")

    # 3. Synthesize & Upload full poem continuous audio
    full_text = "，".join([item.get("hanzi", "") for item in lines]) + "。"
    out_full = os.path.join(tmp_audio_dir, "full_poem.wav")
    logger.info(f"Synthesizing full poem: '{full_text}'...")
    generate_poem_audio_omnivoice_strict(full_text, out_full, voice_sample)

    if folder_id:
        drive_mgr.upload_file(out_full, "full_poem.wav", folder_id, mime_type="audio/wav")

    logger.info("OmniVoice voice generation & Google Drive upload completed 100%!")


if __name__ == "__main__":
    main()
