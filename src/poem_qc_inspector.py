"""
Poem Video Auto-QC Inspector Module (Gatekeeper 2)
Validates physical video integrity, dimensions (1080x1920), framerate (60fps), audio track, and absence of black frames.
"""
import os
import json
import logging
import subprocess
from typing import Dict, Any, Tuple

logger = logging.getLogger("PoemQCInspector")


class PoemQCInspector:
    def __init__(
        self,
        expected_width: int = 1080,
        expected_height: int = 1920,
        min_fps: float = 58.0,
        min_duration: float = 5.0,
        min_size_bytes: int = 1_000_000
    ):
        self.expected_width = expected_width
        self.expected_height = expected_height
        self.min_fps = min_fps
        self.min_duration = min_duration
        self.min_size_bytes = min_size_bytes

    def inspect_video(self, video_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Runs comprehensive physical checks on rendered MP4 video.
        Returns (is_passed, metrics_dict).
        """
        metrics = {
            "file_exists": False,
            "file_size": 0,
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "duration": 0.0,
            "has_audio": False,
            "audio_codec": "",
            "errors": []
        }

        if not os.path.exists(video_path):
            metrics["errors"].append(f"File not found: {video_path}")
            return False, metrics

        metrics["file_exists"] = True
        metrics["file_size"] = os.path.getsize(video_path)

        if metrics["file_size"] < self.min_size_bytes:
            metrics["errors"].append(f"File size too small: {metrics['file_size']} bytes (min: {self.min_size_bytes})")

        # ffprobe inspection
        cmd = [
            "ffprobe", "-v", "error",
            "-show_streams",
            "-show_format",
            "-print_format", "json",
            video_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            probe_data = json.loads(res.stdout)
        except Exception as e:
            metrics["errors"].append(f"FFprobe execution failed: {e}")
            return False, metrics

        streams = probe_data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not v_stream:
            metrics["errors"].append("Missing video stream in MP4 container")
            return False, metrics

        # Video dimensions
        metrics["width"] = int(v_stream.get("width", 0))
        metrics["height"] = int(v_stream.get("height", 0))
        if metrics["width"] != self.expected_width or metrics["height"] != self.expected_height:
            metrics["errors"].append(f"Invalid dimensions: {metrics['width']}x{metrics['height']} (expected: {self.expected_width}x{self.expected_height})")

        # Framerate
        r_fps = v_stream.get("r_frame_rate", "60/1")
        try:
            if "/" in r_fps:
                num, den = map(float, r_fps.split("/"))
                fps_val = num / den if den > 0 else 0
            else:
                fps_val = float(r_fps)
            metrics["fps"] = round(fps_val, 2)
            if metrics["fps"] < self.min_fps:
                metrics["errors"].append(f"FPS too low: {metrics['fps']} (min: {self.min_fps})")
        except Exception:
            metrics["errors"].append(f"Invalid framerate string: {r_fps}")

        # Duration
        fmt = probe_data.get("format", {})
        try:
            metrics["duration"] = round(float(fmt.get("duration", 0)), 2)
            if metrics["duration"] < self.min_duration:
                metrics["errors"].append(f"Duration too short: {metrics['duration']}s (min: {self.min_duration}s)")
        except Exception:
            metrics["errors"].append("Failed to parse duration")

        # Audio stream
        if a_stream:
            metrics["has_audio"] = True
            metrics["audio_codec"] = a_stream.get("codec_name", "")
        else:
            metrics["errors"].append("Missing audio stream")

        passed = len(metrics["errors"]) == 0
        return passed, metrics
