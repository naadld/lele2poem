"""
Script to execute Poem Auto-QC Gatekeeper 2 on GitHub Actions Runner.
Inspects physical video files, validates quality, and updates status to 'Ready'.
"""
import os
import sys
import argparse
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunPoemQC")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.drive_manager import DriveManager
from src.gsheet_manager import PoemGSheetManager
from src.poem_qc_inspector import PoemQCInspector


def send_telegram_alert(message: str):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or "1187577977"
    if not bot_token:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        logger.warning(f"Telegram notification error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID on Google Sheet (#)")
    parser.add_argument("--video-path", type=str, default="", help="Direct local path to video file if already rendered")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    logger.info(f"=== Starting Auto-QC Gatekeeper for Row #{row_id} ===")

    gsheet_mgr = PoemGSheetManager()
    drive_mgr = DriveManager()
    inspector = PoemQCInspector()

    poem_data = gsheet_mgr.get_poem_by_row_id(row_id)
    if not poem_data:
        raise ValueError(f"Could not find poem data for Row #{row_id}")

    topic = poem_data.get("topic", "")
    folder_id = poem_data.get("folder_id", "")
    poem_id = poem_data.get("poem_id", f"{int(row_id):02d}_poem")
    video_url = poem_data.get("video_url", "")

    # Locate local video or download from Drive
    local_vid = args.video_path
    if not local_vid or not os.path.exists(local_vid):
        local_vid = os.path.join(BASE_DIR, "projects", poem_id, "output", f"{poem_id}.mp4")

    if not os.path.exists(local_vid) and folder_id:
        logger.info(f"Downloading video from Drive folder {folder_id} for QC inspection...")
        files = drive_mgr.list_files_in_folder(folder_id)
        vid_file = next((f for f in files if f.get("name", "").endswith(".mp4")), None)
        if vid_file:
            os.makedirs(os.path.dirname(local_vid), exist_ok=True)
            drive_mgr.download_file_by_id(vid_file["id"], local_vid)

    if not os.path.exists(local_vid):
        raise FileNotFoundError(f"Cannot locate video file to QC for Row #{row_id}")

    logger.info(f"Inspecting video: {local_vid}...")
    passed, metrics = inspector.inspect_video(local_vid)

    if passed:
        logger.info(f"✅ AUTO-QC PASSED for Row #{row_id} ({topic})!")
        logger.info(f"Metrics: {metrics['width']}x{metrics['height']} @ {metrics['fps']}fps, Duration: {metrics['duration']}s, Size: {metrics['file_size']/1024/1024:.2f}MB")
        gsheet_mgr.update_status(row_id, "Ready")
        
        msg = (
            f"<b>✅ [Poem Auto-QC Passed] Video Thơ Sẵn Sàng Đăng!</b>\n\n"
            f"• <b>Dòng (#):</b> #{row_id}\n"
            f"• <b>Bài thơ:</b> {topic}\n"
            f"• <b>Kích thước:</b> {metrics['width']}x{metrics['height']} (60fps)\n"
            f"• <b>Thời lượng:</b> {metrics['duration']}s\n"
            f"• <b>Trạng thái Sheet:</b> <code>Ready</code>\n"
            f"• <b>Drive Video:</b> {video_url or 'Đã lưu trên Drive'}"
        )
        send_telegram_alert(msg)
    else:
        logger.error(f"❌ AUTO-QC FAILED for Row #{row_id}: {metrics['errors']}")
        gsheet_mgr.update_status(row_id, "QC_Rejected")
        msg = (
            f"<b>🚨 [Poem Auto-QC Failed] Lỗi Kiểm Định Video Thơ!</b>\n\n"
            f"• <b>Dòng (#):</b> #{row_id}\n"
            f"• <b>Bài thơ:</b> {topic}\n"
            f"• <b>Lỗi:</b> {', '.join(metrics['errors'])}\n"
            f"• <b>Trạng thái Sheet:</b> <code>QC_Rejected</code>"
        )
        send_telegram_alert(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
