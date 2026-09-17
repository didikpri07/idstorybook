"""Shared pytest fixtures for Phase 2 API and integration tests."""

import asyncio

import pytest


@pytest.fixture(scope='session')
def event_loop_runner():
    """Single event loop for all Motor-backed async helpers in this test run."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()