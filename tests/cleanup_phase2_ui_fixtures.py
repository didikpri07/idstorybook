"""Cleanup test-only UI fixture documents for Phase 2 browser validation."""

from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values('/app/backend/.env')
MONGO_URL = BACKEND_ENV.get('MONGO_URL')
DB_NAME = BACKEND_ENV.get('DB_NAME')


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        db.stories.delete_many({'id': {'$regex': '^TEST_UI_'}})
        db.guest_sessions.delete_many({'story_id': {'$regex': '^TEST_UI_'}})
        db.users.delete_many({'email': {'$regex': '^test_ui_parent_'}})
        print('Cleaned TEST_UI fixtures')
    finally:
        client.close()


if __name__ == '__main__':
    main()