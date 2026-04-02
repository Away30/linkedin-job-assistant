#!/usr/bin/env python3
"""Manual testing script for automation modules."""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.automation.job_searcher import job_searcher
from app.automation.human_simulator import HumanSimulator


async def test_job_searcher_url_building():
    """Test job search URL construction."""
    print("\n=== Testing Job Searcher URL Building ===")
    
    test_cases = [
        {
            "name": "Basic search",
            "params": {"keywords": "Python", "location": "San Francisco"},
            "expected": ["keywords=Python", "location=San Francisco"]
        },
        {
            "name": "With easy apply filter",
            "params": {"keywords": "Backend", "easy_apply": True},
            "expected": ["keywords=Backend", "f_AL=true"]
        },
        {
            "name": "With experience level",
            "params": {"keywords": "Engineer", "experience_level": "senior"},
            "expected": ["keywords=Engineer", "f_E=4"]
        },
        {
            "name": "Full search",
            "params": {
                "keywords": "Python",
                "location": "Remote",
                "job_type": "full-time",
                "experience_level": "mid-senior",
                "easy_apply": True
            },
            "expected": ["keywords=Python", "location=Remote", "f_JT=F", "f_E=4", "f_AL=true"]
        }
    ]
    
    for test in test_cases:
        url = job_searcher.build_search_url(**test["params"])
        passed = all(expected in url for expected in test["expected"])
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test['name']}")
        if not passed:
            print(f"  Expected: {test['expected']}")
            print(f"  URL: {url}")
        else:
            print(f"  URL: {url}")


async def test_human_simulator():
    """Test human simulator."""
    print("\n=== Testing Human Simulator ===")
    
    human = HumanSimulator()
    print("✓ HumanSimulator instantiated")
    
    # Test random delays (just verify they work)
    print("Testing random_delay(1-3s)...", end="", flush=True)
    import time
    start = time.time()
    await human.random_delay(1, 3)
    elapsed = time.time() - start
    if elapsed >= 0.9:  # Allow some tolerance
        print(f" ✓ PASS ({elapsed:.2f}s)")
    else:
        print(f" ✗ FAIL ({elapsed:.2f}s < 1s)")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("LinkedIn Job Assistant - Manual Automation Tests")
    print("=" * 60)
    
    try:
        await test_job_searcher_url_building()
        await test_human_simulator()
        
        print("\n" + "=" * 60)
        print("✓ All manual tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
