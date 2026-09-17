"""Seed test-only UI fixtures for Phase 2 browser validation."""

import hashlib
import json
import secrets
from datetime import datetime, timezone

from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values('/app/backend/.env')
MONGO_URL = BACKEND_ENV.get('MONGO_URL')
DB_NAME = BACKEND_ENV.get('DB_NAME')
QA_STORY_ID = 'e62b417b-03b1-4278-99a7-3e4c5d00d386'


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _guest_fixture_id(prefix):
    return f"TEST_UI_{prefix}_{secrets.token_hex(4)}"


def _new_token(prefix):
    return f"test_ui_{prefix}_{secrets.token_hex(10)}"


def _minimal_story_from_qa(qa_story, story_id, status, guest_hash, pages, page_count=None):
    return {
        'id': story_id,
        'user_id': None,
        'guest_id': guest_hash,
        'ownership': 'guest',
        'child_name': qa_story.get('child_name', 'Maya'),
        'title': qa_story.get('title', 'TEST UI Story'),
        'age': qa_story.get('age', 6),
        'gender': qa_story.get('gender', 'Curious'),
        'theme': qa_story.get('theme', 'Moonlit Forest'),
        'visual_style': qa_story.get('visual_style', 'Classic Watercolor'),
        'story_language': qa_story.get('story_language', 'en'),
        'voice_id': qa_story.get('voice_id', 'onyx'),
        'narrator_voice': qa_story.get('narrator_voice', 'Algenib'),
        'page_count': page_count or qa_story.get('page_count', len(pages) if pages else 8),
        'pages': pages,
        'cover': qa_story.get('cover') or {'title': qa_story.get('title', 'TEST UI Story'), 'image': qa_story.get('cover_image')},
        'cover_image': qa_story.get('cover_image'),
        'status': status,
        'stage': 'complete' if status == 'complete' else ('narrating' if status == 'partial' else 'writing'),
        'current_page': len(pages) if status in {'partial', 'complete'} else 1,
        'created_at': now_iso(),
    }


def main():
    if not MONGO_URL or not DB_NAME:
        raise RuntimeError('Missing MONGO_URL or DB_NAME in backend/.env')

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        qa_story = db.stories.find_one({'id': QA_STORY_ID}, {'_id': 0})
        if not qa_story:
            raise RuntimeError(f'QA story {QA_STORY_ID} not found')

        # Clean stale test-only fixtures from previous runs.
        db.stories.delete_many({'id': {'$regex': '^TEST_UI_'}})
        db.guest_sessions.delete_many({'story_id': {'$regex': '^TEST_UI_'}})
        db.users.delete_many({'email': {'$regex': '^test_ui_parent_' }})

        pages_complete = qa_story.get('pages', [])
        pages_partial = [dict(pages_complete[0]), dict(pages_complete[1])] if len(pages_complete) >= 2 else pages_complete[:]
        for p in pages_partial:
            p['complete'] = True

        # Guest claim fixture story (completed)
        guest_claim_story_id = _guest_fixture_id('GUESTCLAIM')
        guest_claim_token = _new_token('guestclaim')
        guest_claim_hash = hashlib.sha256(guest_claim_token.encode()).hexdigest()
        guest_claim_story = _minimal_story_from_qa(qa_story, guest_claim_story_id, 'complete', guest_claim_hash, pages_complete)
        db.stories.insert_one(guest_claim_story)
        db.guest_sessions.insert_one({'guest_id': guest_claim_hash, 'story_id': guest_claim_story_id, 'created_at': datetime.now(timezone.utc)})

        # Progress transition fixtures (start generating; updater script moves terminal states)
        prog_complete_story_id = _guest_fixture_id('PROGCOMP')
        prog_complete_token = _new_token('progcomp')
        prog_complete_hash = hashlib.sha256(prog_complete_token.encode()).hexdigest()
        prog_complete_story = _minimal_story_from_qa(qa_story, prog_complete_story_id, 'generating', prog_complete_hash, [], page_count=8)
        db.stories.insert_one(prog_complete_story)

        prog_partial_story_id = _guest_fixture_id('PROGPART')
        prog_partial_token = _new_token('progpart')
        prog_partial_hash = hashlib.sha256(prog_partial_token.encode()).hexdigest()
        prog_partial_story = _minimal_story_from_qa(qa_story, prog_partial_story_id, 'generating', prog_partial_hash, [], page_count=8)
        db.stories.insert_one(prog_partial_story)

        # Legacy no-timestamp reader fixture
        legacy_story_id = _guest_fixture_id('LEGACY')
        legacy_token = _new_token('legacy')
        legacy_hash = hashlib.sha256(legacy_token.encode()).hexdigest()
        legacy_pages = [dict(pages_complete[0])] if pages_complete else []
        if legacy_pages:
            legacy_pages[0]['sentence_timestamps'] = []
            legacy_pages[0]['complete'] = True
        legacy_story = _minimal_story_from_qa(qa_story, legacy_story_id, 'complete', legacy_hash, legacy_pages, page_count=1)
        db.stories.insert_one(legacy_story)

        # Mobile 32-page dots fixture
        dots_story_id = _guest_fixture_id('DOTS32')
        dots_token = _new_token('dots32')
        dots_hash = hashlib.sha256(dots_token.encode()).hexdigest()
        dots_pages = []
        source_pages = pages_complete[:]
        for i in range(32):
            src = dict(source_pages[i % len(source_pages)]) if source_pages else {
                'image': '/api/images/placeholder.png',
                'audio': None,
                'sentence_timestamps': [],
                'duration_ms': None,
            }
            dots_pages.append({
                'page': i + 1,
                'text': src.get('text', f'TEST page {i + 1}.'),
                'image': src.get('image'),
                'audio': src.get('audio'),
                'duration_ms': src.get('duration_ms'),
                'sentence_timestamps': src.get('sentence_timestamps', []),
                'complete': True,
            })
        dots_story = _minimal_story_from_qa(qa_story, dots_story_id, 'complete', dots_hash, dots_pages, page_count=32)
        db.stories.insert_one(dots_story)

        fixture_data = {
            'guest_claim': {'story_id': guest_claim_story_id, 'guest_token': guest_claim_token},
            'progress_complete': {'story_id': prog_complete_story_id, 'guest_token': prog_complete_token},
            'progress_partial': {'story_id': prog_partial_story_id, 'guest_token': prog_partial_token},
            'legacy_no_timestamps': {'story_id': legacy_story_id, 'guest_token': legacy_token},
            'mobile_dots_32': {'story_id': dots_story_id, 'guest_token': dots_token},
            'qa_story_id': QA_STORY_ID,
            'created_at': now_iso(),
        }
        with open('/app/tests/phase2_ui_fixture_data.json', 'w', encoding='utf-8') as f:
            json.dump(fixture_data, f, indent=2)

        print(json.dumps(fixture_data, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()