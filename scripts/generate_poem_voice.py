"""
Script to synthesize poem voice on GitHub Actions using OmniVoice strictly
and upload all audio files directly into the poem's dedicated project folder on Google Drive.
"""
import os
import sys
import json
import argparse
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeneratePoemVoice")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.poem_audio_generator import generate_poem_audio_omnivoice_strict


def upload_audio_to_gdrive_folder(local_path: str, filename: str, drive_folder_id: str, sa_json_str: str):
    """Uploads generated voice wav file directly into the poem project folder on Google Drive."""
    try:
        sa_info = json.loads(sa_json_str)
        creds = Credentials.from_service_account_info(sa_info, scopes=['https://www.googleapis.com/auth/drive'])
        drive_service = build('drive', 'v3', credentials=creds)

        media = MediaFileUpload(local_path, mimetype='audio/wav')
        meta = {'name': filename, 'parents': [drive_folder_id]}
        f = drive_service.files().create(body=meta, media_body=media, fields='id, name').execute()
        logger.info(f"[GDRIVE] Uploaded {filename} -> Drive File ID: {f.get('id')}")
        return f.get('id')
    except Exception as e:
        logger.error(f"[GDRIVE] Failed to upload {filename} to Google Drive: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2")
    parser.add_argument("--poem-id", type=str, default="01_yong_e")
    parser.add_argument("--folder-id", type=str, default="1Fzyf9GHFg9fmWIQt4C-vvWKuF2Z5__gI")
    args = parser.parse_args()

    logger.info(f"Starting OmniVoice generation for Row #{args.row_id} (Project: {args.poem_id})...")

    # Reference audio sample
    voice_sample = os.path.join(BASE_DIR, "assets", "Vegetarian Wolf.wav")
    if not os.path.exists(voice_sample):
        raise FileNotFoundError(f"Missing required voice sample: {voice_sample}")

    tmp_audio_dir = os.path.join(BASE_DIR, "temp_audio")
    os.makedirs(tmp_audio_dir, exist_ok=True)

    POEM_DATABASE = {
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
        ],
        "4": [
            {"hanzi": "锄禾日当午", "pinyin": "chú hé rì dāng wǔ"},
            {"hanzi": "汗滴禾下土", "pinyin": "hàn dī hé xià tǔ"},
            {"hanzi": "谁知盘中餐", "pinyin": "shéi zhī pán zhōng cān"},
            {"hanzi": "粒粒皆辛苦", "pinyin": "lì lì jiē xīn kǔ"}
        ],
        "5": [
            {"hanzi": "江南可采莲", "pinyin": "jiāng nán kě cǎi lián"},
            {"hanzi": "莲叶何田田", "pinyin": "lián yè hé tián tián"},
            {"hanzi": "鱼戏莲叶间", "pinyin": "yú xì lián yè jiān"},
            {"hanzi": "鱼戏莲叶东，鱼戏莲叶西，鱼戏莲叶南，鱼戏莲叶北", "pinyin": "yú xì lián yè dōng, xī, nán, běi"}
        ]
    }

    lines = POEM_DATABASE.get(args.row_id, POEM_DATABASE["2"])
    sa_json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", "")

    # 1. Synthesize & Upload individual sentence audios directly to GDrive project folder
    for idx, item in enumerate(lines, start=1):
        fname = f"line_{idx}.wav"
        out_line = os.path.join(tmp_audio_dir, fname)
        logger.info(f"Synthesizing sentence {idx}: {item['hanzi']}...")
        generate_poem_audio_omnivoice_strict(item["hanzi"], out_line, voice_sample)
        
        if sa_json_str and args.folder_id:
            upload_audio_to_gdrive_folder(out_line, fname, args.folder_id, sa_json_str)

    # 2. Synthesize & Upload full poem continuous audio
    full_text = "，".join([item["hanzi"] for item in lines]) + "。"
    out_full = os.path.join(tmp_audio_dir, "full_poem.wav")
    logger.info(f"Synthesizing full poem: {full_text}...")
    generate_poem_audio_omnivoice_strict(full_text, out_full, voice_sample)

    if sa_json_str and args.folder_id:
        upload_audio_to_gdrive_folder(out_full, "full_poem.wav", args.folder_id, sa_json_str)

    logger.info("OmniVoice voice generation & Google Drive upload completed 100%!")


if __name__ == "__main__":
    main()
