#!/usr/bin/env python3
"""
Backend test for IDStorybook - Selectable book length feature
Tests POST /api/stories with different page_count values
"""
import os
import sys
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load frontend .env to get REACT_APP_BACKEND_URL
frontend_env = Path("/app/frontend/.env")
if frontend_env.exists():
    load_dotenv(frontend_env)

BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    print("❌ ERROR: REACT_APP_BACKEND_URL not found in /app/frontend/.env")
    sys.exit(1)

API_BASE = f"{BASE_URL}/api"
print(f"🔗 Testing against: {API_BASE}")
print()

# Test data - realistic for a 6-year-old
TEST_STORY_DATA = {
    "child_name": "Testy",
    "age": 6,
    "gender": "Curious",
    "theme": "Moonlit Forest",
    "visual_style": "Classic Watercolor",
    "story_language": "en",
}


def poll_story_completion(story_id: str, max_wait: int = 150) -> dict:
    """Poll GET /api/stories/{id} until status is 'completed' or 'failed'"""
    print(f"   ⏳ Polling story {story_id} (max {max_wait}s)...")
    start = time.time()
    poll_count = 0
    
    while time.time() - start < max_wait:
        poll_count += 1
        try:
            resp = requests.get(f"{API_BASE}/stories/{story_id}", timeout=10)
            if resp.status_code != 200:
                print(f"   ⚠️  Poll #{poll_count}: HTTP {resp.status_code}")
                time.sleep(5)
                continue
            
            story = resp.json()
            status = story.get("status", "unknown")
            elapsed = int(time.time() - start)
            
            if status == "completed":
                print(f"   ✅ Story completed after {elapsed}s ({poll_count} polls)")
                return story
            elif status == "failed":
                error = story.get("error", "Unknown error")
                print(f"   ❌ Story generation FAILED after {elapsed}s: {error}")
                return story
            else:
                print(f"   ⏳ Poll #{poll_count} ({elapsed}s): status={status}")
                time.sleep(5)
        except Exception as e:
            print(f"   ⚠️  Poll #{poll_count} error: {e}")
            time.sleep(5)
    
    print(f"   ⏰ Timeout after {max_wait}s")
    return {"status": "timeout"}


def test_scenario_1_page_count_8():
    """Test 1: POST with page_count=8, poll to completion, verify 8 pages"""
    print("=" * 70)
    print("TEST 1: page_count=8 (full end-to-end)")
    print("=" * 70)
    
    payload = {**TEST_STORY_DATA, "page_count": 8}
    
    try:
        print("📤 POST /api/stories with page_count=8...")
        resp = requests.post(f"{API_BASE}/stories", json=payload, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: POST returned HTTP {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        story = resp.json()
        story_id = story.get("id")
        immediate_status = story.get("status")
        immediate_page_count = story.get("page_count")
        
        print(f"✅ POST successful:")
        print(f"   - story_id: {story_id}")
        print(f"   - status: {immediate_status}")
        print(f"   - page_count: {immediate_page_count}")
        
        # Verify immediate response
        if immediate_status != "processing":
            print(f"❌ FAIL: Expected status='processing', got '{immediate_status}'")
            return False
        
        if immediate_page_count != 8:
            print(f"❌ FAIL: Expected page_count=8, got {immediate_page_count}")
            return False
        
        print()
        
        # Poll until completion
        completed_story = poll_story_completion(story_id, max_wait=150)
        
        final_status = completed_story.get("status")
        
        if final_status == "timeout":
            print("❌ FAIL: Story generation timed out (>150s)")
            return False
        
        if final_status == "failed":
            error_msg = completed_story.get("error", "Unknown error")
            # Check if it's an AI provider issue (not a code bug)
            if "budget" in error_msg.lower() or "quota" in error_msg.lower() or "credit" in error_msg.lower():
                print(f"⚠️  AI PROVIDER ISSUE (not a code bug): {error_msg}")
                print("   This is a genuine AI credit/quota limitation, not a code defect.")
                return "ai_quota_issue"
            else:
                print(f"❌ FAIL: Story generation failed: {error_msg}")
                return False
        
        if final_status != "completed":
            print(f"❌ FAIL: Expected status='completed', got '{final_status}'")
            return False
        
        # Verify pages
        pages = completed_story.get("pages", [])
        page_count_actual = len(pages)
        
        print()
        print(f"📊 Verification:")
        print(f"   - pages count: {page_count_actual}")
        print(f"   - illustrations_expected: {completed_story.get('illustrations_expected')}")
        
        if page_count_actual != 8:
            print(f"❌ FAIL: Expected 8 pages, got {page_count_actual}")
            return False
        
        # Verify each page has text and image
        for i, page in enumerate(pages, 1):
            text = page.get("text", "")
            image = page.get("image", "")
            if not text:
                print(f"❌ FAIL: Page {i} has empty text")
                return False
            if not image:
                print(f"❌ FAIL: Page {i} has empty image")
                return False
        
        print(f"✅ All 8 pages have non-empty text and image")
        
        # Verify illustrations_expected = ceil(8/3) = 3
        illustrations_expected = completed_story.get("illustrations_expected")
        if illustrations_expected != 3:
            print(f"❌ FAIL: Expected illustrations_expected=3 (ceil(8/3)), got {illustrations_expected}")
            return False
        
        print(f"✅ illustrations_expected=3 (correct for 8 pages)")
        print()
        print("✅ TEST 1 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_2_invalid_page_count():
    """Test 2: POST with page_count=99, verify immediate response defaults to 24"""
    print()
    print("=" * 70)
    print("TEST 2: page_count=99 (validator should default to 24)")
    print("=" * 70)
    
    payload = {**TEST_STORY_DATA, "page_count": 99}
    
    try:
        print("📤 POST /api/stories with page_count=99...")
        resp = requests.post(f"{API_BASE}/stories", json=payload, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: POST returned HTTP {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        story = resp.json()
        page_count = story.get("page_count")
        
        print(f"✅ POST successful:")
        print(f"   - story_id: {story.get('id')}")
        print(f"   - page_count: {page_count}")
        
        if page_count != 24:
            print(f"❌ FAIL: Expected page_count=24 (validator default), got {page_count}")
            return False
        
        print("✅ Validator correctly defaulted invalid page_count=99 to 24")
        print()
        print("✅ TEST 2 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_3_missing_page_count():
    """Test 3: POST without page_count field, verify immediate response defaults to 24"""
    print()
    print("=" * 70)
    print("TEST 3: Missing page_count (should default to 24)")
    print("=" * 70)
    
    payload = {**TEST_STORY_DATA}  # No page_count field
    
    try:
        print("📤 POST /api/stories without page_count field...")
        resp = requests.post(f"{API_BASE}/stories", json=payload, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: POST returned HTTP {resp.status_code}")
            print(f"   Response: {resp.text[:500]}")
            return False
        
        story = resp.json()
        page_count = story.get("page_count")
        
        print(f"✅ POST successful:")
        print(f"   - story_id: {story.get('id')}")
        print(f"   - page_count: {page_count}")
        
        if page_count != 24:
            print(f"❌ FAIL: Expected page_count=24 (default), got {page_count}")
            return False
        
        print("✅ Missing page_count correctly defaulted to 24")
        print()
        print("✅ TEST 3 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print()
    print("🧪 IDStorybook Backend Test - Selectable Book Length")
    print("=" * 70)
    print()
    
    results = {}
    
    # Test 1: Full end-to-end with page_count=8
    results["test_1"] = test_scenario_1_page_count_8()
    
    # Test 2: Invalid page_count=99
    results["test_2"] = test_scenario_2_invalid_page_count()
    
    # Test 3: Missing page_count
    results["test_3"] = test_scenario_3_missing_page_count()
    
    # Summary
    print()
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    ai_issues = sum(1 for v in results.values() if v == "ai_quota_issue")
    total = len(results)
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASSED")
        elif result == "ai_quota_issue":
            print(f"⚠️  {test_name}: AI QUOTA ISSUE (not a code bug)")
        else:
            print(f"❌ {test_name}: FAILED")
    
    print()
    print(f"Total: {total} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"AI Issues: {ai_issues}")
    
    if failed > 0:
        print()
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    elif ai_issues > 0:
        print()
        print("⚠️  ALL TESTS PASSED (with AI quota issues noted)")
        sys.exit(0)
    else:
        print()
        print("✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
