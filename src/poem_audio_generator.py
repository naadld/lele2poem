"""
Poem Audio Generator Module
STRICT MANDATE: 100% OmniVoice Voice Cloning ONLY (Zero-shot synthesis with Vegetarian Wolf.wav).
NO generic TTS or Edge-TTS.
"""
import os
import sys
import logging
import numpy as np
import scipy.io.wavfile as wavfile
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OmniVoicePoemGenerator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_SAMPLE_PATH = os.path.join(BASE_DIR, "assets", "Vegetarian Wolf.wav")


def save_tensor_as_wav(wav_tensor, output_path: str, sample_rate: int = 24000):
    """
    Save torch audio tensor directly via scipy/soundfile to prevent torchcodec dependency errors.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if hasattr(wav_tensor, "squeeze"):
        audio_np = wav_tensor.squeeze().cpu().numpy()
    else:
        audio_np = np.array(wav_tensor)

    # Normalize & convert to int16 PCM
    if audio_np.dtype != np.int16:
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = audio_np / max_val
        audio_np = (audio_np * 32767).clip(-32768, 32767).astype(np.int16)

    wavfile.write(output_path, sample_rate, audio_np)
    logger.info(f"[OMNIVOICE] Saved clean audio wav to: {output_path}")


def generate_poem_audio_omnivoice_strict(
    text: str,
    output_path: str,
    ref_audio_path: str = VOICE_SAMPLE_PATH,
    lang_id: str = "cmn" # Mandarin Chinese
) -> str:
    """
    Synthesize poem audio using STRICTLY OmniVoice Voice Cloning.
    """
    if not os.path.exists(ref_audio_path):
        raise FileNotFoundError(f"Reference voice sample not found at: {ref_audio_path}")

    logger.info(f"[OMNIVOICE-STRICT] Synthesizing audio for text: '{text}'...")
    logger.info(f"[OMNIVOICE-STRICT] Reference sample: '{ref_audio_path}'")

    from omnivoice import OmniVoice

    # Load model
    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice")
    wav = model.generate(
        text=text,
        ref_audio=ref_audio_path,
        lang_id=lang_id
    )

    save_tensor_as_wav(wav, output_path, sample_rate=24000)
    return output_path


def synthesize_all_poem_lines(
    poem_id: str,
    lines: List[Dict[str, str]],
    project_dir: str
) -> Dict[str, Any]:
    """
    Synthesize 4 individual sentence audio clips + 1 full poem audio clip via OmniVoice.
    """
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    results = {}
    
    # 1. Synthesize each individual line
    for idx, item in enumerate(lines, start=1):
        line_text = item.get("hanzi", "")
        line_pinyin = item.get("pinyin", "")
        line_out = os.path.join(audio_dir, f"line_{idx}.wav")
        
        logger.info(f"[OMNIVOICE-STRICT] Generating Line {idx}: {line_text} ({line_pinyin})...")
        generate_poem_audio_omnivoice_strict(line_text, line_out)
        results[f"line_{idx}"] = line_out

    # 2. Synthesize full poem continuous recitation
    full_text = "，".join([item.get("hanzi", "") for item in lines]) + "。"
    full_out = os.path.join(audio_dir, "full_poem.wav")
    logger.info(f"[OMNIVOICE-STRICT] Generating Full Poem: {full_text}...")
    generate_poem_audio_omnivoice_strict(full_text, full_out)
    results["full_poem"] = full_out
    
    return results


if __name__ == "__main__":
    sample_text = "鹅，鹅，鹅，曲项向天歌。白毛浮绿水，红掌拨清波。"
    out_file = os.path.join(BASE_DIR, "projects", "01_yong_e", "audio", "full_poem.wav")
    generate_poem_audio_omnivoice_strict(sample_text, out_file)
