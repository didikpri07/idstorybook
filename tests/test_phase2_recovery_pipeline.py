"""Phase 2 deterministic recovery tests for generation checkpoints/retry and audio timing."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pymongo import MongoClient


if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from generation import generate, sentence_timestamps  # noqa: E402


# Module: DB fixtures and deterministic story builders
BACKEND_ENV = dotenv_values('/app/backend/.env')
MONGO_URL = os.environ.get('MONGO_URL') or BACKEND_ENV.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME') or BACKEND_ENV.get('DB_NAME')
AUDIO_DIR = Path('/app/backend/generated_audio')


@pytest.fixture(scope='session')
def assert_env_ready():
    assert MONGO_URL, 'MONGO_URL is required'
    assert DB_NAME, 'DB_NAME is required'


@pytest.fixture(scope='session')
def mongo(assert_env_ready):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        yield db
    finally:
        client.close()


@pytest.fixture(autouse=True)
def cleanup_test_recovery_docs(mongo):
    yield
    mongo.stories.delete_many({'id': {'$regex': '^TEST_RECOVERY_'}})


@pytest.fixture(scope='session')
def sample_audio_urls():
    wav_files = sorted(AUDIO_DIR.glob('*.wav'))
    mp3_files = sorted(AUDIO_DIR.glob('*.mp3'))
    if not wav_files:
        pytest.skip('No WAV audio available in /app/backend/generated_audio for timing tests')
    if not mp3_files:
        pytest.skip('No MP3 audio available in /app/backend/generated_audio for timing tests')
    return {
        'wav': f"/api/audio/{wav_files[0].name}",
        'mp3': f"/api/audio/{mp3_files[0].name}",
    }


def _draft(page_count=2):
    pages = []
    prompts = []
    for idx in range(page_count):
        pages.append({'page': idx + 1, 'text': f'TEST page {idx + 1}. A second sentence.'})
        prompts.append(f'TEST illustration prompt {idx + 1}')
    return {
        'title': 'TEST Recovery Story',
        'cover_title': 'TEST Recovery Cover',
        'cover_prompt': 'TEST cover prompt',
        'illustration_prompts': prompts,
        'pages': pages,
    }


def _insert_story(mongo, *, story_id, voice_id='nova', page_count=2, pages=None, generation_draft=None, status='generating'):
    now_iso = datetime.now(timezone.utc).isoformat()
    story = {
        'id': story_id,
        'child_name': 'TEST Child',
        'age': 6,
        'gender': 'Curious',
        'theme': 'Moonlit Forest',
        'visual_style': 'Classic Watercolor',
        'story_language': 'en',
        'page_count': page_count,
        'voice_id': voice_id,
        'narrator_voice': 'TEST Voice',
        'status': status,
        'stage': 'writing',
        'current_page': 1,
        'pages': pages or [],
        'cover': {},
        'cover_image': '/api/images/placeholder.png',
        'generation_draft': generation_draft,
        'created_at': now_iso,
    }
    mongo.stories.insert_one(story)


# Module: generate() checkpoint retention and missing-step-only retry behavior
def test_generate_partial_then_retry_image_timeout_retains_progress(mongo, sample_audio_urls, event_loop_runner):
    story_id = f'TEST_RECOVERY_IMG_{uuid.uuid4().hex[:10]}'
    _insert_story(mongo, story_id=story_id, voice_id='shimmer', page_count=2)

    state = {'image_calls': [], 'narration_calls': [], 'fail_image_once': True}

    async def text_fn(*args, **kwargs):
        return _draft(page_count=2)

    async def image_fn(prompt, theme, age, photo, index, style):
        state['image_calls'].append(index)
        if index == 1 and state['fail_image_once']:
            state['fail_image_once'] = False
            raise asyncio.TimeoutError('simulated image timeout')
        return '/api/images/placeholder.png'

    async def narration_fn(text, index, language, voice_id):
        state['narration_calls'].append((index, voice_id))
        return sample_audio_urls['wav']

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    partial = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert partial['status'] == 'partial'
    assert len(partial['pages']) == 2
    assert partial['pages'][0]['complete'] is True
    assert partial['pages'][0]['image'] and partial['pages'][0]['audio']
    assert partial['pages'][1]['image'] is None
    assert partial['pages'][1]['audio'] is None

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    completed = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert completed['status'] == 'complete'
    assert completed['completed_pages'] == 2
    page_numbers = [p['page'] for p in completed['pages']]
    assert len(page_numbers) == len(set(page_numbers))
    assert state['image_calls'].count(0) == 1
    assert state['narration_calls'] == [(0, 'shimmer'), (1, 'shimmer')]


def test_generate_partial_then_retry_audio_none_only_retries_missing_audio(mongo, sample_audio_urls, event_loop_runner):
    story_id = f'TEST_RECOVERY_AUD_{uuid.uuid4().hex[:10]}'
    _insert_story(mongo, story_id=story_id, voice_id='nova', page_count=2)

    state = {'image_calls': [], 'narration_calls': [], 'fail_audio_once': True}

    async def text_fn(*args, **kwargs):
        return _draft(page_count=2)

    async def image_fn(prompt, theme, age, photo, index, style):
        state['image_calls'].append(index)
        return '/api/images/placeholder.png'

    async def narration_fn(text, index, language, voice_id):
        state['narration_calls'].append((index, voice_id))
        if index == 1 and state['fail_audio_once']:
            state['fail_audio_once'] = False
            return None
        return sample_audio_urls['mp3']

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    partial = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert partial['status'] == 'partial'
    assert partial['pages'][1]['image'] is not None
    assert partial['pages'][1]['audio'] is None

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    completed = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert completed['status'] == 'complete'
    assert state['image_calls'].count(1) == 1
    assert state['narration_calls'].count((0, 'nova')) == 1
    assert state['narration_calls'].count((1, 'nova')) == 2


def test_generate_failure_before_any_page_keeps_zero_pages_and_partial_status(mongo, event_loop_runner):
    story_id = f'TEST_RECOVERY_EARLY_{uuid.uuid4().hex[:10]}'
    _insert_story(mongo, story_id=story_id, page_count=2)

    async def text_fn(*args, **kwargs):
        raise asyncio.TimeoutError('simulated text timeout')

    async def image_fn(*args, **kwargs):
        raise AssertionError('image_fn must not be called when text generation fails')

    async def narration_fn(*args, **kwargs):
        raise AssertionError('narration_fn must not be called when text generation fails')

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    story = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert story['status'] == 'partial'
    assert story['pages'] == []


def test_generate_completed_audio_without_timing_adds_missing_timestamps_only(mongo, sample_audio_urls, event_loop_runner):
    story_id = f'TEST_RECOVERY_TIMING_{uuid.uuid4().hex[:10]}'
    text = 'First sentence. Second sentence.'
    prebuilt_pages = [{
        'page': 1,
        'text': text,
        'image': '/api/images/placeholder.png',
        'audio': sample_audio_urls['wav'],
        'sentence_timestamps': [],
        'complete': False,
    }]
    prebuilt_draft = {
        'title': 'TEST Existing Draft',
        'cover_title': 'TEST Existing Cover',
        'cover_prompt': 'TEST cover prompt',
        'illustration_prompts': ['TEST illustration prompt 1'],
        'pages': [{'page': 1, 'text': text}],
    }
    _insert_story(
        mongo,
        story_id=story_id,
        page_count=1,
        pages=prebuilt_pages,
        generation_draft=prebuilt_draft,
        status='partial',
    )
    mongo.stories.update_one({'id': story_id}, {'$set': {'cover': {'title': 'TEST Existing Cover', 'image': '/api/images/placeholder.png'}}})

    async def text_fn(*args, **kwargs):
        raise AssertionError('text_fn must not be called when generation_draft already exists')

    async def image_fn(*args, **kwargs):
        raise AssertionError('image_fn must not be called for completed image page')

    async def narration_fn(*args, **kwargs):
        raise AssertionError('narration_fn must not be called for completed audio page')

    event_loop_runner.run_until_complete(generate(story_id, text_fn, image_fn, narration_fn, AUDIO_DIR))
    story = mongo.stories.find_one({'id': story_id}, {'_id': 0})
    assert story['status'] == 'complete'
    page = story['pages'][0]
    assert page['duration_ms'] > 0
    assert len(page['sentence_timestamps']) >= 2
    assert page['complete'] is True


# Module: direct sentence timing duration extraction for WAV and MP3
def test_sentence_timestamps_extracts_duration_for_wav_and_mp3(sample_audio_urls):
    text = 'A tiny test sentence. Another tiny sentence.'
    wav_duration, wav_timings = sentence_timestamps(text, sample_audio_urls['wav'], AUDIO_DIR)
    mp3_duration, mp3_timings = sentence_timestamps(text, sample_audio_urls['mp3'], AUDIO_DIR)

    assert wav_duration > 0
    assert mp3_duration > 0
    assert wav_timings[-1]['end_ms'] == wav_duration
    assert mp3_timings[-1]['end_ms'] == mp3_duration