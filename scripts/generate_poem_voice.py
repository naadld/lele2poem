"""
Script to synthesize poem voice on GitHub Actions using OmniVoice strictly.
3-Stage Pipeline:
  Stage 1: Model & Environment Caching (Hugging Face weights + Pip packages)
  Stage 2: Individual Sentence Voice Generation (line_1.wav -> line_4.wav)
  Stage 3: Master Audio Merge (Combining 4 lines with natural poetic pauses into full_poem.wav) & Google Drive Upload
"""
import os
import sys
import json
import argparse
import logging
import numpy as np
import scipy.io.wavfile as wavfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeneratePoemVoice")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.poem_audio_generator import generate_poem_audio_omnivoice_strict
from src.drive_manager import DriveManager
from src.gsheet_manager import PoemGSheetManager


def merge_sentence_audios_to_full_poem(
    line_audio_paths: list,
    output_full_path: str,
    pause_seconds: float = 0.55,
    sample_rate: int = 24000
) -> str:
    """
    Stage 3: Merges all generated line WAV files with natural poetic pause gaps
    into one final master full_poem.wav.
    """
    logger.info(f"[STAGE-3 MERGE] Merging {len(line_audio_paths)} sentence audios (pause: {pause_seconds}s)...")
    combined_audio = []
    pause_samples = int(pause_seconds * sample_rate)
    silence = np.zeros(pause_samples, dtype=np.int16)

    for idx, path in enumerate(line_audio_paths):
        if not os.path.exists(path):
            logger.warning(f"Audio file missing for merge: {path}")
            continue
        sr, data = wavfile.read(path)
        # Ensure 1D int16
        data = np.squeeze(data).flatten().astype(np.int16)
        combined_audio.append(data)
        if idx < len(line_audio_paths) - 1:
            combined_audio.append(silence)

    if combined_audio:
        master_audio = np.concatenate(combined_audio)
        wavfile.write(output_full_path, sample_rate, master_audio)
        logger.info(f"[STAGE-3 MERGE] Master full poem audio saved: {output_full_path} ({len(master_audio)/sample_rate:.2f}s)")
        return output_full_path
    else:
        raise RuntimeError("No audio clips available to merge.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID on Google Sheet (#)")
    parser.add_argument("--poem-id", type=str, default="", help="Poem Project ID (optional)")
    parser.add_argument("--folder-id", type=str, default="", help="Google Drive Project Folder ID (optional)")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    logger.info(f"=== OMNIVOICE VOICE PIPELINE FOR ROW #{row_id} ===")

    # Reference audio sample
    voice_sample = os.path.join(BASE_DIR, "assets", "Vegetarian Wolf.wav")
    if not os.path.exists(voice_sample):
        raise FileNotFoundError(f"Missing required reference voice sample: {voice_sample}")

    tmp_audio_dir = os.path.join(BASE_DIR, "temp_audio")
    os.makedirs(tmp_audio_dir, exist_ok=True)

    # 1. Fetch Dynamic Data from Google Sheet
    gsheet_mgr = PoemGSheetManager()
    drive_mgr = DriveManager()
    
    poem_data = gsheet_mgr.get_poem_by_row_id(row_id)
    
    lines = []
    folder_id = args.folder_id or ""
    poem_id = args.poem_id or ""

    if poem_data:
        logger.info(f"[GSHEET] Loaded Poem: '{poem_data.get('topic')}' (Level: {poem_data.get('level')})")
        lines = [l for l in poem_data.get("lines", []) if l.get("hanzi")]
        if not folder_id:
            folder_id = poem_data.get("folder_id", "")
        if not poem_id:
            poem_id = poem_data.get("poem_id", "")

    # Fallback to local default if offline
    if not lines:
        logger.warning(f"Using fallback dataset for Row #{row_id}")
        POEM_FALLBACK = {
            "2": [
                {"hanzi": "鹅，鹅，鹅", "pinyin": "é, é, é"},
                {"hanzi": "曲项向天歌", "pinyin": "qū xiàng xiàng tiān gē"},
                {"hanzi": "白毛浮绿水", "pinyin": "bái máo fú lǜ shuǐ"},
                {"hanzi": "红掌拨清波", "pinyin": "hóng zhǎng bō qīng bō"}
            ]
        }
        lines = POEM_FALLBACK.get(row_id, POEM_FALLBACK["2"])
        if not folder_id and row_id == "2":
            folder_id = "1Fzyf9GHFg9fmWIQt4C-vvWKuF2Z5__gI"

    logger.info(f"Loaded {len(lines)} poem lines. Drive Target: {folder_id or 'None'}")

    # =========================================================================
    # KHÂU 2: CHẠY VOICE GENERATION TỪNG CÂU ĐƠN LẺ
    # =========================================================================
    logger.info(">>> KHÂU 2: Sinh giọng ngâm OmniVoice cho từng câu thơ đơn lẻ...")
    generated_line_paths = []

    for idx, item in enumerate(lines, start=1):
        fname = f"line_{idx}.wav"
        out_line = os.path.join(tmp_audio_dir, fname)
        text = item.get("hanzi", "")
        logger.info(f"[KHÂU 2] Đang ngâm câu {idx}: '{text}'...")
        generate_poem_audio_omnivoice_strict(text, out_line, voice_sample)
        generated_line_paths.append(out_line)

        # Upload line audio to Drive
        if folder_id:
            drive_mgr.upload_file(out_line, fname, folder_id, mime_type="audio/wav")

    # =========================================================================
    # KHÂU 3: GỘP CHUNG LẠI THÀNH 1 FILE FINAL (full_poem.wav)
    # =========================================================================
    logger.info(">>> KHÂU 3: Gộp chung các câu ngâm thành 1 file Master Final (full_poem.wav)...")
    out_full = os.path.join(tmp_audio_dir, "full_poem.wav")
    merge_sentence_audios_to_full_poem(
        line_audio_paths=generated_line_paths,
        output_full_path=out_full,
        pause_seconds=0.55,
        sample_rate=24000
    )

    # Upload master full poem audio to Drive
    if folder_id:
        drive_mgr.upload_file(out_full, "full_poem.wav", folder_id, mime_type="audio/wav")

    logger.info("✨ [HOÀN TẤT 3 KHÂU] Voice generation & Master audio merge uploaded to Google Drive 100%!")


if __name__ == "__main__":
    main()
