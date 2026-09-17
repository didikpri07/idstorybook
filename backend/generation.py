"""Durable page checkpoints. Retrying never regenerates a successful asset."""
import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from mutagen import File as AudioFile
from database import db

GOOGLE_VOICES = {'nova': 'Sulafat', 'onyx': 'Algenib', 'shimmer': 'Achernar'}


def sentence_timestamps(text, audio_path, audio_dir):
    file = AudioFile(str(Path(audio_dir) / Path(audio_path).name))
    if file is None or not file.info.length:
        raise ValueError('Audio duration is unavailable')
    duration_ms = max(1, round(file.info.length * 1000))
    sentences = re.findall(r'.+?(?:[.!?]+[\"”’\']*(?=\s|$)|$)', text.strip(), flags=re.S)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        sentences = [text.strip()]
    total_chars = sum(len(s) for s in sentences)
    cursor = 0
    elapsed_chars = 0
    timings = []
    for sentence in sentences:
        elapsed_chars += len(sentence)
        end = round(duration_ms * elapsed_chars / max(1, total_chars))
        timings.append({'sentence': sentence, 'start_ms': cursor, 'end_ms': end})
        cursor = end
    return duration_ms, timings


def progress_of(story):
    total = story.get('page_count') or len(story.get('pages', [])) or 24
    pages = story.get('pages') or []
    completed = sum(bool(p.get('image') and p.get('audio')) for p in pages)
    written = len((story.get('generation_draft') or {}).get('pages', []))
    units = written + sum(bool(p.get('image')) + bool(p.get('audio')) for p in pages)
    units += int(bool((story.get('cover') or {}).get('image')))
    status = story.get('status', 'completed')
    if status == 'completed':
        status = 'complete'
    if status == 'processing':
        status = 'generating'
    if status == 'failed':
        status = 'partial'
    percent = 100 if status == 'complete' else min(99, math.floor(100 * units / (total * 3 + 1)))
    return {'status': status, 'current_page': story.get('current_page', completed), 'total_pages': total,
            'stage': story.get('stage', 'complete' if status == 'complete' else 'writing'),
            'completed_pages': total if status == 'complete' else completed, 'percent': percent,
            'estimated_seconds_remaining': 0 if status == 'complete' else max(13, (total - completed) * 13),
            'error': story.get('error')}


async def generate(story_id, text_fn, image_fn, narration_fn, audio_dir):
    async def save(**fields):
        fields['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.stories.update_one({'id': story_id}, {'$set': fields})

    try:
        story = await db.stories.find_one({'id': story_id}, {'_id': 0})
        if not story:
            return
        data = story.get('generation_draft')
        if not data:
            await save(stage='writing', current_page=1)
            data = await asyncio.wait_for(text_fn(
                story['child_name'], story['age'], story['gender'], story['theme'], story['story_language'],
                story_prompt=story.get('story_prompt'), page_count=story['page_count']), timeout=150)
            await save(generation_draft=data, title=data['title'], current_page=story['page_count'])
        pages = story.get('pages') or []
        photo = story.get('generation_photo')
        cover = story.get('cover') or {}

        async def illustration(prompt, index):
            result = await asyncio.wait_for(image_fn(prompt, story['theme'], story['age'], photo, index,
                                                       story.get('visual_style', 'Classic Watercolor')), timeout=180)
            if not result:
                raise RuntimeError('illustration_unavailable')
            return result

        if not cover.get('image'):
            await save(stage='illustrating_cover', current_page=0)
            cover_image = await illustration(data.get('cover_prompt') or data['illustration_prompts'][0], -1)
            cover = {'title': data.get('cover_title') or data['title'], 'image': cover_image}
            await save(cover=cover, cover_image=cover_image)

        for index, page_data in enumerate(data['pages']):
            if index >= len(pages):
                pages.append({'page': index + 1, 'text': page_data['text'], 'image': None, 'audio': None,
                              'sentence_timestamps': [], 'complete': False})
                await save(pages=pages, stage='writing', current_page=index + 1)
            page = pages[index]
            if not page.get('image'):
                await save(stage='illustrating', current_page=index + 1)
                page['image'] = await illustration(data['illustration_prompts'][index], index)
                await save(pages=pages)
            if not page.get('audio'):
                await save(stage='narrating', current_page=index + 1)
                page['audio'] = await asyncio.wait_for(narration_fn(page['text'], index,
                    story['story_language'], story.get('voice_id', 'nova')), timeout=150)
                if not page['audio']:
                    raise RuntimeError('narration_unavailable')
                # Persist the expensive audio before computing timing, so a retry reuses it.
                await save(pages=pages)
            if not page.get('sentence_timestamps'):
                duration, timings = sentence_timestamps(page['text'], page['audio'], audio_dir)
                page.update(duration_ms=duration, sentence_timestamps=timings)
            page['complete'] = True
            await save(pages=pages, completed_pages=index + 1)
        await save(status='complete', stage='complete', current_page=story['page_count'], error=None,
                   illustrations_generated=len(pages), narrations_generated=len(pages))
        await db.stories.update_one({'id': story_id}, {'$unset': {'generation_photo': '', 'generation_draft': ''}})
    except Exception as exc:
        # Preserve all checkpoints; never expose provider secrets or error payloads.
        logging.warning('Generation paused for story %s (%s)', story_id, type(exc).__name__)
        message = 'Generation paused because the AI service could not complete this step. Your progress is saved.'
        await save(status='partial', error=message)