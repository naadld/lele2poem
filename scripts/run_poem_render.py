"""
Script to execute Poem Video Rendering on GitHub Actions Runner.
1. Downloads images and audio from Google Drive project folder / Artifacts
2. Renders 9:16 Vertical Video (1080x1920 60fps) with 3-Tier Karaoke
3. Uploads final MP4 to Google Drive project folder using GDriveUploader (Method 3: OAuth 2.0)
4. Updates Google Sheet row status to 'Video'
"""
import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunPoemRender")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.drive_manager import DriveManager
from src.gdrive_uploader import GDriveUploader
from src.gsheet_manager import PoemGSheetManager
from src.poem_video_renderer import render_full_poem_video


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID on Google Sheet (#)")
    parser.add_argument("--poem-id", type=str, default="", help="Poem Project ID (e.g. 01_yong_e)")
    parser.add_argument("--folder-id", type=str, default="", help="Google Drive Project Folder ID")
    parser.add_argument("--upload-gdrive", action="store_true", default=True, help="Upload rendered video to Drive")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    logger.info(f"=== Starting Poem Video Render Pipeline for Row #{row_id} ===")

    gsheet_mgr = PoemGSheetManager()
    drive_mgr = DriveManager()

    poem_data = gsheet_mgr.get_poem_by_row_id(row_id)
    if not poem_data:
        raise ValueError(f"Could not retrieve poem data for Row #{row_id} from Google Sheets.")

    topic = poem_data.get("topic", "《咏鹅》")
    level = poem_data.get("level", "HSK 1-2")
    lines = poem_data.get("lines", [])
    folder_id = args.folder_id or poem_data.get("folder_id", "")
    poem_id = args.poem_id or poem_data.get("poem_id", f"{int(row_id):02d}_poem")

    logger.info(f"Target Poem: '{topic}', Level: '{level}', Project ID: '{poem_id}'")
    logger.info(f"Google Drive Project Folder ID: '{folder_id}'")

    if not folder_id:
        raise ValueError(f"Missing Google Drive folder ID for Row #{row_id}")

    # Local workspace for runner
    proj_dir = os.path.join(BASE_DIR, "projects", poem_id)
    img_dir = os.path.join(proj_dir, "images")
    audio_dir = os.path.join(proj_dir, "audio")
    out_dir = os.path.join(proj_dir, "output")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Download missing image assets from Google Drive folder
    logger.info(f"Checking project assets from Google Drive folder: {folder_id}...")
    drive_files = drive_mgr.list_files_in_folder(folder_id)
    logger.info(f"Found {len(drive_files)} file(s) in Drive folder.")

    for f in drive_files:
        name = f.get("name", "")
        fid = f.get("id", "")
        if not name or not fid:
            continue
        if name.endswith(".jpeg") or name.endswith(".jpg") or name.endswith(".png"):
            dest = os.path.join(img_dir, name)
            if not os.path.exists(dest):
                drive_mgr.download_file_by_id(fid, dest)
        elif name.endswith(".wav") or name.endswith(".mp3"):
            dest = os.path.join(audio_dir, name)
            if not os.path.exists(dest):
                drive_mgr.download_file_by_id(fid, dest)

    # 2. Render Video
    output_filename = f"{poem_id}.mp4"
    output_mp4_path = os.path.join(out_dir, output_filename)
    
    logger.info(f"Rendering 9:16 vertical video -> {output_mp4_path}...")
    render_full_poem_video(
        project_dir=proj_dir,
        output_mp4=output_mp4_path,
        topic=topic,
        level=level,
        lines_data=lines,
        cover_duration=0.75
    )

    # 3. Upload rendered MP4 to Google Drive Project Folder using GDriveUploader (OAuth 2.0)
    video_url = ""
    if args.upload_gdrive and os.path.exists(output_mp4_path):
        logger.info(f"Uploading {output_filename} to Google Drive folder: {folder_id} via GDriveUploader...")
        try:
            uploader = GDriveUploader(folder_id=folder_id)
            uploaded = uploader.upload_file(output_mp4_path, output_filename, mimetype="video/mp4")
            if uploaded and uploaded.get("webViewLink"):
                video_url = uploaded.get("webViewLink")
                logger.info(f"✅ Google Drive Video Link: {video_url}")
        except Exception as ue:
            logger.warning(f"GDriveUploader error: {ue}. Falling back to DriveManager...")
            uploaded = drive_mgr.upload_file(
                local_path=output_mp4_path,
                filename=output_filename,
                folder_id=folder_id,
                mime_type="video/mp4"
            )
            if uploaded and uploaded.get("webViewLink"):
                video_url = uploaded.get("webViewLink")

        if video_url:
            # 4. Update Google Sheet
            gsheet_mgr.update_video_info(row_id, video_url, status="Video")
            logger.info(f"Updated Google Sheet Row #{row_id} with Status: 'Video'")
        else:
            gsheet_mgr.update_video_info(row_id, f"https://github.com/naadld/lele2poem/actions", status="Video")
            logger.info(f"Updated Google Sheet Row #{row_id} with Artifact Status: 'Video'")

    logger.info("=== Poem Video Render Pipeline Completed Successfully! ===")


if __name__ == "__main__":
    main()
