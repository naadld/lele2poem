"""
Cleanup Residual GitHub Actions Artifacts after successful Google Drive upload.
"""
import os
import sys
import argparse
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CleanupArtifacts")


def cleanup_project_artifacts(row_id: str, poem_id: str = "", delete_video: bool = False):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "naadld/lele2poem")

    if not token:
        logger.warning("No GitHub token available. Skipping artifact cleanup.")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/actions/artifacts"
    try:
        res = requests.get(url, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        artifacts = data.get("artifacts", [])
        logger.info(f"Total repository artifacts found: {len(artifacts)}")

        target_prefixes = [f"poem-voice-{row_id}"]
        if delete_video:
            target_prefixes.append(f"poem-video-{row_id}")

        for art in artifacts:
            name = art.get("name", "")
            art_id = art.get("id")
            for prefix in target_prefixes:
                if name == prefix or name.startswith(f"{prefix}-"):
                    del_url = f"https://api.github.com/repos/{repo}/actions/artifacts/{art_id}"
                    del_res = requests.delete(del_url, headers=headers, timeout=20)
                    if del_res.status_code in [200, 204]:
                        logger.info(f"🗑️ Successfully deleted residual artifact: {name} (ID: {art_id})")
                    else:
                        logger.warning(f"Failed to delete artifact {name}: status {del_res.status_code}")
    except Exception as e:
        logger.warning(f"Error during artifact cleanup: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", type=str, default="2", help="Row ID (#)")
    parser.add_argument("--poem-id", type=str, default="", help="Poem Project ID")
    parser.add_argument("--delete-video", action="store_true", default=False, help="Also delete final video artifact")
    args = parser.parse_args()

    row_id = args.row_id.replace("#", "").strip()
    cleanup_project_artifacts(row_id, args.poem_id, args.delete_video)


if __name__ == "__main__":
    main()
