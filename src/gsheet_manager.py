"""
Google Sheets Manager for Poem Module (lele2poem)
Tab: 'poem'
Spreadsheet ID: 1b6LNl7JHRiCsjK1w9VuD86GLqAfmSOtDUOm5whrGdH0
Strict Mandate: Row Number == Row ID (#)
"""
import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
import gspread
from google.oauth2.service_account import Credentials
from src.config import SPREADSHEET_ID, POEM_SHEET_TAB, SERVICE_ACCOUNT_PATHS

logger = logging.getLogger("PoemGSheetManager")


class PoemGSheetManager:
    def __init__(self, sa_json_str: Optional[str] = None, sa_path: Optional[str] = None):
        self.spreadsheet_id = SPREADSHEET_ID
        self.tab_name = POEM_SHEET_TAB
        self.client = None
        self.sheet = None
        self._authenticate(sa_json_str, sa_path)

    def _authenticate(self, sa_json_str: Optional[str], sa_path: Optional[str]):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = None
        # 1. Env vars
        env_json = (
            sa_json_str
            or os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
            or os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
            or os.environ.get("SERVICE_ACCOUNT_JSON")
        )
        if env_json and env_json.strip():
            try:
                info = json.loads(env_json)
                creds = Credentials.from_service_account_info(info, scopes=scopes)
            except Exception as e:
                logger.warning(f"Failed to parse credentials from env JSON: {e}")

        # 2. File paths
        if not creds:
            search_paths = [sa_path] if sa_path else []
            search_paths.extend(SERVICE_ACCOUNT_PATHS)
            for p in search_paths:
                if p and os.path.exists(p):
                    try:
                        creds = Credentials.from_service_account_file(p, scopes=scopes)
                        break
                    except Exception as e:
                        logger.warning(f"Failed to load creds from {p}: {e}")

        if creds:
            try:
                self.client = gspread.authorize(creds)
                spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                self.sheet = spreadsheet.worksheet(self.tab_name)
                logger.info(f"[GSHEET] Connected to tab '{self.tab_name}' successfully.")
            except Exception as e:
                logger.error(f"[GSHEET] Failed to open worksheet: {e}")
        else:
            logger.warning("[GSHEET] Could not authenticate with Google Sheets.")

    @staticmethod
    def extract_folder_id(drive_url_or_id: str) -> str:
        """Extracts Google Drive folder ID from URL or raw ID string."""
        if not drive_url_or_id:
            return ""
        drive_url_or_id = drive_url_or_id.strip()
        match = re.search(r'folders/([a-zA-Z0-9_-]+)', drive_url_or_id)
        if match:
            return match.group(1)
        if "/" not in drive_url_or_id and len(drive_url_or_id) > 15:
            return drive_url_or_id
        return drive_url_or_id

    @staticmethod
    def parse_line_cell(cell_val: str) -> Dict[str, str]:
        """Parses cell formatted as: 'pinyin | hanzi | vietnamese'."""
        if not cell_val:
            return {"pinyin": "", "hanzi": "", "vietnamese": ""}
        parts = [p.strip() for p in cell_val.split("|")]
        pinyin = parts[0] if len(parts) > 0 else ""
        hanzi = parts[1] if len(parts) > 1 else ""
        vietnamese = parts[2] if len(parts) > 2 else ""
        return {
            "pinyin": pinyin,
            "hanzi": hanzi,
            "vietnamese": vietnamese
        }

    def get_poem_by_row_id(self, row_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch row data by row_id (#) ensuring Row Number == #.
        Row 2 on sheet corresponds to #2.
        """
        if not self.sheet:
            logger.error("Worksheet is not connected.")
            return None

        clean_id = str(row_id).replace("#", "").strip()
        try:
            row_num = int(clean_id)
        except ValueError:
            logger.error(f"Invalid row_id: {row_id}")
            return None

        try:
            row_values = self.sheet.row_values(row_num)
            if not row_values:
                logger.warning(f"Row {row_num} is empty.")
                return None

            # Pad row values to match 18 standard columns
            while len(row_values) < 18:
                row_values.append("")

            # Parse 4 lines
            lines = [
                self.parse_line_cell(row_values[4]),  # Câu 1 (Col E)
                self.parse_line_cell(row_values[5]),  # Câu 2 (Col F)
                self.parse_line_cell(row_values[6]),  # Câu 3 (Col G)
                self.parse_line_cell(row_values[7])   # Câu 4 (Col H)
            ]

            folder_raw = row_values[11]  # Col L: image folder
            folder_id = self.extract_folder_id(folder_raw)

            # Project ID from Notes or generated from row
            notes = row_values[17]
            poem_id = f"{int(clean_id):02d}_poem"
            match = re.search(r'Poem project:\s*([a-zA-Z0-9_-]+)', notes)
            if match:
                poem_id = match.group(1)

            return {
                "row_id": clean_id,
                "row_number": row_num,
                "topic": row_values[1],
                "level": row_values[2],
                "status": row_values[3],
                "lines": lines,
                "full_poem": row_values[8],
                "metadata": row_values[9],
                "image_prompt": row_values[10],
                "image_folder_url": folder_raw,
                "folder_id": folder_id,
                "video_url": row_values[12],
                "notes": notes,
                "poem_id": poem_id
            }
        except Exception as e:
            logger.error(f"Failed to get row {row_num} from Google Sheet: {e}")
            return None

    def update_status(self, row_id: str, status: str) -> bool:
        """Update Status (Col D / Col 4) for a given row."""
        if not self.sheet:
            return False
        clean_id = str(row_id).replace("#", "").strip()
        try:
            row_num = int(clean_id)
            self.sheet.update_cell(row_num, 4, status)
            logger.info(f"[GSHEET] Updated Row #{row_num} Status -> '{status}'")
            return True
        except Exception as e:
            logger.error(f"[GSHEET] Failed to update status for Row #{clean_id}: {e}")
            return False

    def update_video_info(self, row_id: str, video_url: str, status: str = "Video") -> bool:
        """Update Video URL (Col M / Col 13) and Status (Col D / Col 4)."""
        if not self.sheet:
            return False
        clean_id = str(row_id).replace("#", "").strip()
        try:
            row_num = int(clean_id)
            self.sheet.update_cell(row_num, 13, video_url)
            self.sheet.update_cell(row_num, 4, status)
            logger.info(f"[GSHEET] Updated Row #{row_num} Video URL -> '{video_url}', Status -> '{status}'")
            return True
        except Exception as e:
            logger.error(f"[GSHEET] Failed to update video info for Row #{clean_id}: {e}")
            return False
