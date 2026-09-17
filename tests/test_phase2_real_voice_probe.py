"""Real Google voice probes for Sulafat (EN) and Achernar (ID) using server.generate_narration."""

import os
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values


if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from generation import sentence_timestamps  # noqa: E402
from server import generate_narration  # noqa: E402


BACKEND_ENV = dotenv_values('/app/backend/.env')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or BACKEND_ENV.get('GEMINI_API_KEY')
AUDIO_DIR = Path('/app/backend/generated_audio')


# Module: real provider narration probes (no mocks)
def test_real_google_voice_probe_sulafat_and_achernar(event_loop_runner):
    if not GEMINI_API_KEY:
        pytest.skip('GEMINI_API_KEY is not configured')

    en_audio = event_loop_runner.run_until_complete(
        generate_narration('Hello from a tiny Sulafat test.', idx=9001, language='en', voice_id='nova')
    )
    id_audio = event_loop_runner.run_until_complete(
        generate_narration('Halo, ini uji suara Achernar yang sangat singkat.', idx=9002, language='id', voice_id='shimmer')
    )

    assert isinstance(en_audio, str) and en_audio.startswith('/api/audio/')
    assert isinstance(id_audio, str) and id_audio.startswith('/api/audio/')

    en_path = AUDIO_DIR / Path(en_audio).name
    id_path = AUDIO_DIR / Path(id_audio).name
    assert en_path.exists() and en_path.stat().st_size > 0
    assert id_path.exists() and id_path.stat().st_size > 0

    en_duration, _ = sentence_timestamps('Hello from a tiny Sulafat test.', en_audio, AUDIO_DIR)
    id_duration, _ = sentence_timestamps('Halo, ini uji suara Achernar yang sangat singkat.', id_audio, AUDIO_DIR)
    assert en_duration > 0
    assert id_duration > 0