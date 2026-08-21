"""
Script to synthesize poem voice on GitHub Actions using OmniVoice strictly.
Supports modular execution:
  --action synthesize : Generates line_1.wav -> line_4.wav via OmniVoice
  --action merge      : Concatenates lines with poetic pauses into full_poem.wav
  --action upload     : Uploads all generated wav files to Google Drive project folder
  --action summary    : Emits Markdown summary to $GITHUB_STEP_SUMMARY
  --action all        : Executes all steps sequentially
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


def get_poem_metadata(row_id: str, custom_poem_id: str = "", custom_folder_id: str = ""):
    """Fetch poem details from Google Sheet or fallback."""
    gsheet_mgr = PoemGSheetManager()
    poem_data = gsheet_mgr.get_poem_by_row_id(row_id)
    
    lines = []
    folder_id = custom_folder_id or ""
    poem_id = custom_poem_id or ""
    topic = "《咏鹅》"
    level = "HSK 1-2"

    if poem_data:
        topic = poem_data.get("topic", topic)
        level = poem_data.get("level", level)
        lines = [l for l in poem_data.get("lines", []) if l.get("hanzi")]
        if not folder_id:
            folder_id = poem_data.get("folder_id", "")
        if not poem_id:
            poem_id = poem_data.get("poem_id", "")

    if not lines:
        POEM_FALLBACK = {
            "2": [
                {"hanzi": "鹅，鹅，鹅", "pinyin": "é, é, é", "vietnamese": "Thiên nga, thiên nga"},
                {"hanzi": "曲项向天歌", "pinyin": "qū xiàng xiàng tiān gē", "vietnamese": "Vươn cổ cất tiếng hót"},
                {"hanzi": "白毛浮绿水", "pinyin": "bái máo fú lǜ shuǐ", "vietnamese": "Lông trắng nổi trên nước biếc"},
                {"hanzi": "红掌拨清波", "pinyin": "hóng zhǎng bō qīng bō", "vietnamese": "Mái chèo hồng rẽ sóng trong"}
            ]
        }
        lines = POEM_FALLBACK.get(row_id, POEM_FALLBACK["2"])
        if not folder_id and row_id == "2":
            folder_id = "1Fzyf9GHFg9fmWIQt4C-vvWKuF2Z5__gI"

    if not poem_id:
        poem_id = f"{int(row_id):02d}_poem"

    return {
        "row_id": row_id,
        "poem_id": poem_id,
        "topic": topic,
        "level": level,
        "lines": lines,
        "folder_id": folder_id
    }


def step_synthesize(meta: dict, tmp_dir: str):
    """Step: Synthesize 4 sentence audio clips."""
    voice_sample = os.path.join(BASE_DIR, "assets", "Vegetarian Wolf.wav")
    if not os.path.exists(voice_sample):
        raise FileNotFoundError(f"Missing voice sample: {voice_sample}")

    lines = meta["lines"]
    logger.info(f"🎙️ [BƯỚC 1: SINH CÂU LẺ] Bắt đầu sinh {len(lines)} câu thơ đơn lẻ...")
    
    for idx, item in enumerate(lines, start=1):
        text = item.get("hanzi", "")
        fname = f"line_{idx}.wav"
        out_path = os.path.join(tmp_dir, fname)
        print(f"::group::🎙️ Đang ngâm Câu {idx}: '{text}' ({item.get('pinyin')})")
        generate_poem_audio_omnivoice_strict(text, out_path, voice_sample)
        print("::endgroup::")
        logger.info(f"✅ Đã sinh xong Câu {idx} -> {fname}")


def step_merge(meta: dict, tmp_dir: str, pause_seconds: float = 0.55):
    """Step: Merge sentence audios into full_poem.wav."""
    lines = meta["lines"]
    line_paths = [os.path.join(tmp_dir, f"line_{i}.wav") for i in range(1, len(lines) + 1)]
    out_full = os.path.join(tmp_dir, "full_poem.wav")

    logger.info(f"🎼 [BƯỚC 2: GỘP AUDIO MASTER] Đang gộp {len(line_paths)} câu thơ thành 1 file final...")
    combined = []
    sr = 24000
    silence = np.zeros(int(pause_seconds * sr), dtype=np.int16)

    for idx, path in enumerate(line_paths):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing line audio for merge: {path}")
        s_rate, data = wavfile.read(path)
        sr = s_rate
        data = np.squeeze(data).flatten().astype(np.int16)
        combined.append(data)
        if idx < len(line_paths) - 1:
            combined.append(silence)

    master = np.concatenate(combined)
    wavfile.write(out_full, sr, master)
    dur = len(master) / sr
    logger.info(f"✨ [BƯỚC 2 HOÀN TẤT] File Master: {out_full} (Thời lượng: {dur:.2f}s, {len(master)} samples)")


def step_upload(meta: dict, tmp_dir: str):
    """Step: Upload all generated wav files to Google Drive."""
    folder_id = meta.get("folder_id", "")
    if not folder_id:
        logger.warning("No Google Drive folder ID found. Skipping upload.")
        return

    drive_mgr = DriveManager()
    logger.info(f"☁️ [BƯỚC 3: UPLOAD DRIVE] Tải toàn bộ audio lên Drive Folder ID: {folder_id}...")
    
    files_to_upload = [f"line_{i}.wav" for i in range(1, len(meta["lines"]) + 1)] + ["full_poem.wav"]
    for fname in files_to_upload:
        p = os.path.join(tmp_dir, fname)
        if os.path.exists(p):
            uploaded = drive_mgr.upload_file(p, fname, folder_id, mime_type="audio/wav")
            if uploaded:
                logger.info(f"✅ Uploaded {fname} -> Drive ID: {uploaded.get('id')}")


def step_summary(meta: dict, tmp_dir: str):
    """Step: Write GitHub Actions Markdown Summary."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = meta["lines"]
    md = [
        f"## 🎙️ Kết Quả Sinh Giọng Ngâm OmniVoice: {meta['topic']}",
        f"- **Dòng (#):** `#{meta['row_id']}`",
        f"- **Dự án:** `{meta['poem_id']}`",
        f"- **Cấp độ:** `{meta['level']}`",
        f"- **Google Drive Folder ID:** `{meta['folder_id']}`",
        "",
        "### 📑 Chi Tiết Các File Audio",
        "| File | Hán Tự (简体) | Pinyin | Dịch Nghĩa | Kích Thước |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for i, item in enumerate(lines, start=1):
        fname = f"line_{i}.wav"
        fpath = os.path.join(tmp_dir, fname)
        sz = f"{os.path.getsize(fpath)/1024:.1f} KB" if os.path.exists(fpath) else "N/A"
        md.append(f"| `line_{i}.wav` | **{item.get('hanzi')}** | `{item.get('pinyin')}` | *{item.get('vietnamese')}* | {sz} |")

    full_path = os.path.join(tmp_dir, "full_poem.wav")
    full_sz = f"{os.path.getsize(full_path)/1024:.1f} KB" if os.path.exists(full_path) else "N/A"
    md.append(f"| **`full_poem.wav`** | **Toàn bài thơ (Master Final)** | - | - | **{full_sz}** |")
    md.append("")
    md.append("> 🚀 **Trạng thái:** Tự động kích hoạt Render Pipeline 9:16 (1080x1920 60fps).")

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    logger.info("Generated GitHub Step Summary.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID (#)")
    parser.add_argument("--poem-id", type=str, default="", help="Poem Project ID")
    parser.add_argument("--folder-id", type=str, default="", help="Google Drive Folder ID")
    parser.add_argument("--action", type=str, default="all", choices=["synthesize", "merge", "upload", "summary", "all"], help="Action step to run")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    meta = get_poem_metadata(row_id, args.poem_id, args.folder_id)

    # Audio save directory inside project
    tmp_dir = os.path.join(BASE_DIR, "projects", meta["poem_id"], "audio")
    os.makedirs(tmp_dir, exist_ok=True)

    action = args.action.lower()
    if action in ["synthesize", "all"]:
        step_synthesize(meta, tmp_dir)
    if action in ["merge", "all"]:
        step_merge(meta, tmp_dir)
    if action in ["upload", "all"]:
        step_upload(meta, tmp_dir)
    if action in ["summary", "all"]:
        step_summary(meta, tmp_dir)


if __name__ == "__main__":
    main()
