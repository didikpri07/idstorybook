from fastapi import HTTPException, Request
from accounts import get_optional_user, guest_id, digest
from database import db
from story_models import StoryPublic


async def authorized_story(story_id, request: Request, allow_share=False):
    story = await db.stories.find_one({'id': story_id}, {'_id': 0})
    if not story:
        raise HTTPException(404, 'Story not found')
    # Public samples must be deliberately marked; legacy/guest does NOT mean public.
    if allow_share and story.get('is_sample'):
        return story, True
    share = request.query_params.get('share', '')
    if allow_share and share and story.get('share_token_hash') == digest(share):
        return story, True
    user = await get_optional_user(request)
    if user and story.get('user_id') == user['user_id']:
        return story, False
    gid = guest_id(request)
    if not story.get('user_id') and gid and story.get('guest_id') == gid:
        return story, False
    raise HTTPException(404, 'Story not found or access unavailable')


def public_story(story, read_only=False):
    return StoryPublic(**{**story, 'is_guest': not bool(story.get('user_id')), 'read_only': read_only})