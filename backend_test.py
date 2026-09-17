#!/usr/bin/env python3
"""
Backend API test for one unique illustration per page feature.
Tests that sequential image generation (batch_size=1) produces 8 distinct images for an 8-page book.
"""

import requests
import time
import sys
from typing import Dict, Any

# Read backend URL from frontend/.env
def get_backend_url():
    with open('/app/frontend/.env', 'r') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                return line.split('=', 1)[1].strip()
    raise ValueError("REACT_APP_BACKEND_URL not found in /app/frontend/.env")

BASE_URL = get_backend_url()
API_BASE = f"{BASE_URL}/api"

def test_one_illustration_per_page():
    """
    Test that an 8-page book generates 8 unique illustrations (not placeholders).
    Sequential generation with batch_size=1 should avoid HTTP 429 rate limits.
    """
    print("=" * 80)
    print("TEST: One unique illustration per page (8-page book, sequential generation)")
    print("=" * 80)
    
    # Step 1: Create story with page_count=8
    payload = {
        "child_name": "Testy",
        "age": 6,
        "gender": "Curious",
        "theme": "Moonlit Forest",
        "visual_style": "Classic Watercolor",
        "story_language": "en",
        "page_count": 8
    }
    
    print(f"\n1. POST {API_BASE}/stories")
    print(f"   Payload: {payload}")
    
    start_time = time.time()
    
    try:
        response = requests.post(f"{API_BASE}/stories", json=payload, timeout=30)
        response.raise_for_status()
        story_data = response.json()
    except Exception as e:
        print(f"   ❌ FAILED: POST request error: {e}")
        return False
    
    print(f"   ✅ Response status: {response.status_code}")
    print(f"   Story ID: {story_data.get('id')}")
    print(f"   Initial status: {story_data.get('status')}")
    print(f"   Page count: {story_data.get('page_count')}")
    
    # Verify immediate response
    story_id = story_data.get('id')
    if not story_id:
        print("   ❌ FAILED: No story ID in response")
        return False
    
    if story_data.get('status') != 'processing':
        print(f"   ⚠️  WARNING: Expected status 'processing', got '{story_data.get('status')}'")
    
    if story_data.get('page_count') != 8:
        print(f"   ❌ FAILED: Expected page_count=8, got {story_data.get('page_count')}")
        return False
    
    # Step 2: Poll until completed or failed (up to 240 seconds)
    print(f"\n2. Polling GET {API_BASE}/stories/{story_id} (max 240s, interval ~7s)")
    
    max_wait = 240
    poll_interval = 7
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed = time.time() - start_time
        
        try:
            response = requests.get(f"{API_BASE}/stories/{story_id}", timeout=30)
            response.raise_for_status()
            story = response.json()
        except Exception as e:
            print(f"   ⚠️  Poll error at {elapsed:.1f}s: {e}")
            continue
        
        status = story.get('status')
        print(f"   [{elapsed:.1f}s] Status: {status}")
        
        if status == 'completed':
            print(f"   ✅ Story completed in {elapsed:.1f}s")
            break
        elif status == 'failed':
            error_msg = story.get('error', 'Unknown error')
            print(f"   ❌ FAILED: Story generation failed: {error_msg}")
            return False
    else:
        print(f"   ❌ FAILED: Timeout after {max_wait}s, status still '{status}'")
        return False
    
    total_time = time.time() - start_time
    
    # Step 3: Verify the completed story
    print(f"\n3. Verifying completed story (total time: {total_time:.1f}s)")
    
    pages = story.get('pages', [])
    illustrations_expected = story.get('illustrations_expected', 0)
    illustrations_generated = story.get('illustrations_generated', 0)
    
    print(f"   len(pages): {len(pages)}")
    print(f"   illustrations_expected: {illustrations_expected}")
    print(f"   illustrations_generated: {illustrations_generated}")
    
    # Check 1: len(pages) == 8
    if len(pages) != 8:
        print(f"   ❌ FAILED: Expected 8 pages, got {len(pages)}")
        return False
    print("   ✅ len(pages) == 8")
    
    # Check 2: illustrations_expected == 8
    if illustrations_expected != 8:
        print(f"   ❌ FAILED: Expected illustrations_expected=8, got {illustrations_expected}")
        return False
    print("   ✅ illustrations_expected == 8")
    
    # Check 3: illustrations_generated == 8 (all succeeded)
    if illustrations_generated != 8:
        print(f"   ❌ FAILED: Expected illustrations_generated=8, got {illustrations_generated}")
        print("   Some illustrations failed to generate (likely rate limit or API error)")
        return False
    print("   ✅ illustrations_generated == 8")
    
    # Check 4: All pages have non-empty text and image
    for i, page in enumerate(pages, 1):
        text = page.get('text', '')
        image = page.get('image', '')
        
        if not text:
            print(f"   ❌ FAILED: Page {i} has empty text")
            return False
        if not image:
            print(f"   ❌ FAILED: Page {i} has empty image")
            return False
    print("   ✅ All pages have non-empty text and image")
    
    # Check 5: All 8 page images are DISTINCT
    image_urls = [page.get('image', '') for page in pages]
    unique_images = set(image_urls)
    
    print(f"   Number of distinct image URLs: {len(unique_images)}")
    
    if len(unique_images) != 8:
        print(f"   ❌ FAILED: Expected 8 distinct image URLs, got {len(unique_images)}")
        print(f"   Image URLs: {image_urls}")
        return False
    print("   ✅ All 8 page images are DISTINCT")
    
    # Check 6: NONE of the images are placeholders
    placeholder_count = sum(1 for url in image_urls if 'placeholder' in url.lower())
    
    print(f"   Number of placeholder images: {placeholder_count}")
    
    if placeholder_count > 0:
        print(f"   ❌ FAILED: Found {placeholder_count} placeholder images (expected 0)")
        print(f"   Placeholder URLs: {[url for url in image_urls if 'placeholder' in url.lower()]}")
        return False
    print("   ✅ NONE of the 8 page images are placeholders")
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ ALL CHECKS PASSED")
    print("=" * 80)
    print(f"Total time to completion: {total_time:.1f}s")
    print(f"len(pages): {len(pages)}")
    print(f"illustrations_expected: {illustrations_expected}")
    print(f"illustrations_generated: {illustrations_generated}")
    print(f"Distinct image URLs: {len(unique_images)}")
    print(f"Placeholder images: {placeholder_count}")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    print(f"Backend URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print()
    
    success = test_one_illustration_per_page()
    
    if success:
        print("\n✅ TEST PASSED")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED")
        sys.exit(1)
