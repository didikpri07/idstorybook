"""Byte-range audio delivery for reliable browser seeking on the existing Starlette version."""
import re
from pathlib import Path

import anyio
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix='/api/audio')
AUDIO_DIR = Path(__file__).parent / 'generated_audio'


@router.api_route('/{filename}', methods=['GET', 'HEAD'])
async def audio_file(filename: str, request: Request):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+\.(wav|mp3)', filename):
        raise HTTPException(404, 'Audio not found')
    path = AUDIO_DIR / filename
    if not path.is_file():
        raise HTTPException(404, 'Audio not found')
    size = path.stat().st_size
    start, end, status = 0, size - 1, 200
    headers = {'Accept-Ranges': 'bytes'}
    requested_range = request.headers.get('range')
    if requested_range:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested_range)
        if not match or not any(match.groups()):
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:
            start = max(0, size - int(last))
        if start >= size or start > end:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        status = 206
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    headers['Content-Length'] = str(end - start + 1)
    media_type = 'audio/wav' if filename.endswith('.wav') else 'audio/mpeg'
    if request.method == 'HEAD':
        return Response(status_code=status, headers=headers, media_type=media_type)

    async def chunks():
        async with await anyio.open_file(path, 'rb') as stream:
            await stream.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = await stream.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(chunks(), status_code=status, headers=headers, media_type=media_type)