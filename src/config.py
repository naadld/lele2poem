"""
Configuration Module for Poem & Story Video Engine
"""
import os

# Google Sheets Configuration
SPREADSHEET_ID = "1b6LNl7JHRiCsjK1w9VuD86GLqAfmSOtDUOm5whrGdH0"
POEM_SHEET_TAB = "poem"
STORY_SHEET_TAB = "stories"

# Google Drive Storage (Poem & Story Videos)
GDRIVE_POEM_STORY_FOLDER_ID = "17SlqprPl46g4i7q7fmDu-a3VI2xbW8nH"
GDRIVE_POEM_STORY_FOLDER_URL = "https://drive.google.com/drive/u/0/folders/17SlqprPl46g4i7q7fmDu-a3VI2xbW8nH"

# Service Account Credentials Path
SERVICE_ACCOUNT_PATHS = [
    "/media/vpsg16gb/HaRiDisk/Telegram_Command_Center/service_account.json",
    "/media/vpsg16gb/HaRiDisk/CHANNELS/lelehoctiengtrung/service_account.json"
]

# Video Dimensions & Render Specs (9:16 Vertical Video)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 60
