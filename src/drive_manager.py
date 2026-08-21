"""
Google Drive Manager Module for Poem & Story Engines
Lightweight, resilient Google Drive v3 REST API client (No discovery doc freeze).
Supports uploading/downloading assets and project folders.
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from google.oauth2.service_account import Credentials
import google.auth.transport.requests

logger = logging.getLogger("DriveManager")

DEFAULT_SA_PATHS = [
    "/media/vpsg16gb/HaRiDisk/CHANNELS/lelehoctiengtrung/service_account.json",
    "/media/vpsg16gb/HaRiDisk/Telegram_Command_Center/service_account.json",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "service_account.json")
]


class DriveManager:
    def __init__(self, sa_json_str: Optional[str] = None, sa_path: Optional[str] = None):
        self.credentials = self._load_credentials(sa_json_str, sa_path)
        self.session = None
        if self.credentials:
            self._init_session()

    def _load_credentials(self, sa_json_str: Optional[str], sa_path: Optional[str]) -> Optional[Credentials]:
        scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
        # 1. Environment variables
        env_json = (
            sa_json_str
            or os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
            or os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
            or os.environ.get("SERVICE_ACCOUNT_JSON")
        )
        if env_json and env_json.strip():
            try:
                data = json.loads(env_json)
                return Credentials.from_service_account_info(data, scopes=scopes)
            except Exception as e:
                logger.warning(f"Failed to parse credentials from JSON string: {e}")

        # 2. Specified file path
        if sa_path and os.path.exists(sa_path):
            try:
                return Credentials.from_service_account_file(sa_path, scopes=scopes)
            except Exception as e:
                logger.warning(f"Failed to load credentials from {sa_path}: {e}")

        # 3. Default fallback paths
        for path in DEFAULT_SA_PATHS:
            if os.path.exists(path):
                try:
                    return Credentials.from_service_account_file(path, scopes=scopes)
                except Exception as e:
                    logger.warning(f"Failed to load credentials from {path}: {e}")

        logger.warning("No valid Google Service Account credentials found.")
        return None

    def _init_session(self):
        auth_req = google.auth.transport.requests.Request()
        self.credentials.refresh(auth_req)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.credentials.token}"
        })

    def _ensure_token(self):
        if not self.credentials:
            return
        if not self.credentials.valid:
            auth_req = google.auth.transport.requests.Request()
            self.credentials.refresh(auth_req)
            if self.session:
                self.session.headers.update({
                    "Authorization": f"Bearer {self.credentials.token}"
                })

    def list_files_in_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """List all non-trashed files in a Google Drive folder."""
        self._ensure_token()
        if not self.session:
            logger.error("Drive session not authenticated.")
            return []

        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "files(id, name, mimeType, size, webViewLink)",
            "pageSize": 100
        }
        try:
            res = self.session.get(url, params=params, timeout=30)
            res.raise_for_status()
            return res.json().get("files", [])
        except Exception as e:
            logger.error(f"Failed to list files in folder {folder_id}: {e}")
            return []

    def download_file_by_id(self, file_id: str, local_dest: str) -> bool:
        """Download file content from Drive by file ID."""
        self._ensure_token()
        if not self.session:
            return False

        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        try:
            os.makedirs(os.path.dirname(local_dest), exist_ok=True)
            with self.session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(local_dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            logger.info(f"[GDRIVE] Downloaded file ID {file_id} -> {local_dest}")
            return True
        except Exception as e:
            logger.error(f"[GDRIVE] Error downloading file ID {file_id}: {e}")
            return False

    def download_folder_assets(self, folder_id: str, local_dir: str) -> List[str]:
        """Download all files from a Google Drive folder into a local directory."""
        files = self.list_files_in_folder(folder_id)
        os.makedirs(local_dir, exist_ok=True)
        downloaded = []
        for item in files:
            name = item.get("name")
            fid = item.get("id")
            if not name or not fid:
                continue
            dest_path = os.path.join(local_dir, name)
            if self.download_file_by_id(fid, dest_path):
                downloaded.append(dest_path)
        return downloaded

    def upload_file(self, local_path: str, filename: str, folder_id: str, mime_type: str = "application/octet-stream") -> Optional[Dict[str, str]]:
        """Upload a local file to a Google Drive folder (multipart upload)."""
        self._ensure_token()
        if not self.session:
            return None

        if not os.path.exists(local_path):
            logger.error(f"Local file does not exist: {local_path}")
            return None

        metadata = {
            "name": filename,
            "parents": [folder_id]
        }
        files = {
            "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
            "file": (filename, open(local_path, "rb"), mime_type)
        }
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink"
        try:
            # Custom post without standard session header collision on multipart
            headers = {"Authorization": f"Bearer {self.credentials.token}"}
            res = requests.post(url, headers=headers, files=files, timeout=120)
            res.raise_for_status()
            data = res.json()
            logger.info(f"[GDRIVE] Uploaded {filename} -> File ID: {data.get('id')}")
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "webViewLink": data.get("webViewLink") or f"https://drive.google.com/file/d/{data.get('id')}/view"
            }
        except Exception as e:
            logger.error(f"[GDRIVE] Failed to upload {filename}: {e}")
            return None
