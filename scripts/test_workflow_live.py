"""Test the fuel forecast workflow against the live server.

This script tests the workflow using real HTTP requests to the running server,
which helps identify issues that don't appear in TestClient tests.
"""

import requests
import sys
import traceback

BASE_URL = "http://localhost:8000"


def test_workflow():
    """Test the complete fuel forecast workflow."""
    print("=" * 60)
    print("FUEL FORECAST WORKFLOW - LIVE SERVER TEST")
    print("=" * 60)
    
    # Check if server is running
    try:
        r = requests.get(f"{BASE_URL}/", timeout=3)
        print(f"\nServer status: {r.status_code}")
    except Exception as e:
        print(f"\nERROR: Server not running at {BASE_URL}")
        print(f"Start it with: python -m uvicorn src.api.main:app --reload")
        return False
    
    # Start fresh session
    print("\n1. Starting new workflow...")
    r = requests.get(f"{BASE_URL}/fuel-forecast/new", allow_redirects=False)
    location = r.headers.get("Location", "")
    if "/fuel-forecast/" not in location:
        print(f"   ERROR: Could not create session. Location: {location}")
        return False
    
    session_id = location.split("/fuel-forecast/")[1].split("/")[0]
    print(f"   Session ID: {session_id}")
    
    # Step 1: Start Point
    print("\n2. Step 1: Start Point")
    r = requests.post(
        f"{BASE_URL}/fuel-forecast/{session_id}/step/1",
        data={"start_mode": "fresh", "as_of_month": "2025-12"}
    )
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
        return False
    
    # Step 2: Coal Position
    print("\n3. Step 2: Coal Position")
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/2", data={})
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
        return False
    
    # Step 3: Coal Contracts
    print("\n4. Step 3: Coal Contracts")
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/3", data={})
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
        return False
    
    # Step 4: Use Factors - with proper form data
    print("\n5. Step 4: Use Factors")
    form_data = {}
    for month in range(1, 13):
        form_data[f"kc_use_factor_{month}"] = "85"
        form_data[f"cc_use_factor_{month}"] = "85"
        # Ozone months (May-Sep) have 0% for unit 6
        if month in [5, 6, 7, 8, 9]:
            form_data[f"cc_unit6_ozone_use_factor_{month}"] = "0"
        else:
            form_data[f"cc_unit6_ozone_use_factor_{month}"] = "85"
    
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/4", data=form_data)
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
        # Don't return - try to continue
    
    # Step 5: Heat Rates
    print("\n6. Step 5: Heat Rates")
    r = requests.get(f"{BASE_URL}/fuel-forecast/{session_id}/step/5")
    print(f"   GET: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
    
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/5", data={})
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
    
    # Step 6: Generation
    print("\n7. Step 6: Generation")
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/6", data={})
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
    
    # Step 7: Other Costs
    print("\n8. Step 7: Other Costs")
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/7", data={})
    print(f"   POST: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
    
    # Step 8: Review & Save
    print("\n9. Step 8: Review & Save")
    r = requests.get(f"{BASE_URL}/fuel-forecast/{session_id}/step/8")
    print(f"   GET: {r.status_code}")
    if r.status_code >= 400:
        print(f"   ERROR: {r.text[:200]}")
        return False
    
    print("\n" + "=" * 60)
    print(f"SESSION ID FOR BROWSER: {session_id}")
    print(f"URL: {BASE_URL}/fuel-forecast/{session_id}/step/1")
    print("=" * 60)
    
    return True


def test_step4_debug():
    """Debug step 4 specifically."""
    print("\n" + "=" * 60)
    print("STEP 4 DEBUG TEST")
    print("=" * 60)
    
    # Start fresh session
    r = requests.get(f"{BASE_URL}/fuel-forecast/new", allow_redirects=False)
    location = r.headers.get("Location", "")
    session_id = location.split("/fuel-forecast/")[1].split("/")[0]
    print(f"Session ID: {session_id}")
    
    # Complete steps 1-3
    requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/1", 
                  data={"start_mode": "fresh", "as_of_month": "2025-12"})
    requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/2", data={})
    requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/3", data={})
    
    # Test step 4 with empty data
    print("\nTest 1: Step 4 POST with EMPTY data")
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/4", data={})
    print(f"  Status: {r.status_code}")
    if r.status_code >= 400:
        print(f"  Response: {r.text[:500]}")
    
    # Test step 4 with proper form data
    print("\nTest 2: Step 4 POST with FORM data")
    form_data = {}
    for month in range(1, 13):
        form_data[f"kc_use_factor_{month}"] = "85"
        form_data[f"cc_use_factor_{month}"] = "85"
        form_data[f"cc_unit6_ozone_use_factor_{month}"] = "0" if month in [5,6,7,8,9] else "85"
    
    r = requests.post(f"{BASE_URL}/fuel-forecast/{session_id}/step/4", data=form_data)
    print(f"  Status: {r.status_code}")
    if r.status_code >= 400:
        print(f"  Response: {r.text[:500]}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        test_step4_debug()
    else:
        success = test_workflow()
        sys.exit(0 if success else 1)
