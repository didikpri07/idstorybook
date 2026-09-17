"""Update generating UI fixtures to terminal states after short delays for polling checks."""

import json
import time
from datetime import datetime, timezone

from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values('/app/backend/.env')
MONGO_URL = BACKEND_ENV.get('MONGO_URL')
DB_NAME = BACKEND_ENV.get('DB_NAME')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    with open('/app/tests/phase2_ui_fixture_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        qa_story = db.stories.find_one({'id': data['qa_story_id']}, {'_id': 0, 'pages': 1, 'cover': 1, 'cover_image': 1, 'title': 1})
        pages = qa_story.get('pages', []) if qa_story else []

        # Let browser see generating state first.
        time.sleep(4)

        # Transition first fixture to complete.
        complete_story_id = data['progress_complete']['story_id']
        db.stories.update_one(
            {'id': complete_story_id},
            {'$set': {
                'status': 'complete',
                'stage': 'complete',
                'current_page': 8,
                'page_count': 8,
                'pages': pages[:8],
                'cover': qa_story.get('cover'),
                'cover_image': qa_story.get('cover_image'),
                'updated_at': now_iso(),
            }},
        )

        # Transition second fixture to partial with usable finished pages.
        time.sleep(4)
        partial_story_id = data['progress_partial']['story_id']
        partial_pages = [dict(pages[0]), dict(pages[1])] if len(pages) >= 2 else pages[:]
        for p in partial_pages:
            p['complete'] = True
        db.stories.update_one(
            {'id': partial_story_id},
            {'$set': {
                'status': 'partial',
                'stage': 'narrating',
                'current_page': max(1, len(partial_pages)),
                'page_count': 8,
                'pages': partial_pages,
                'error': 'TEST partial transition',
                'updated_at': now_iso(),
            }},
        )

        print('Fixture transitions applied')
    finally:
        client.close()


if __name__ == '__main__':
    main()