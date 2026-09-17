from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SentenceTiming(BaseModel):
    sentence: str
    start_ms: int
    end_ms: int


class StoryPage(BaseModel):
    page: int
    text: str
    image: Optional[str] = None
    audio: Optional[str] = None
    duration_ms: Optional[int] = None
    sentence_timestamps: list[SentenceTiming] = Field(default_factory=list)
    complete: bool = False


class StoryPublic(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    child_name: str = ''
    title: str = ''
    age: Optional[int] = None
    gender: str = ''
    theme: str = ''
    visual_style: str = ''
    story_language: str = 'en'
    page_count: int = 24
    pages: list[StoryPage] = Field(default_factory=list)
    cover: Optional[dict] = None
    cover_image: Optional[str] = None
    created_at: Optional[str] = None
    status: str = 'completed'
    voice_id: str = 'nova'
    narrator_voice: str = 'nova'
    is_guest: bool = False
    read_only: bool = False
    error: Optional[str] = None


class StoryProgress(BaseModel):
    status: str
    current_page: int
    total_pages: int
    stage: str
    completed_pages: int = 0
    percent: int = 0
    estimated_seconds_remaining: int = 0
    error: Optional[str] = None


class OrderPublic(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    story_id: str = ''
    child_name: str = ''
    format: str = ''
    customer_name: str = ''
    email: str = ''
    address: str = ''
    city: str = ''
    postal_code: str = ''
    country: str = ''
    status: str = ''
    payment_status: str = ''
    payment_gateway: str = ''
    created_at: str = ''