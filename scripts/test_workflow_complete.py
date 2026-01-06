"""Test the complete fuel forecast workflow end-to-end."""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

print("=" * 60)
print("FUEL FORECAST WORKFLOW - END TO END TEST")
print("=" * 60)

# Start new workflow
response = client.get('/fuel-forecast/new', follow_redirects=False)
print(f"\n1. Starting new workflow...")
print(f"   Redirect status: {response.status_code}")

# Extract session ID from redirect
location = response.headers.get('location', '')
session_id = None
if '/fuel-forecast/' in location:
    session_id = location.split('/fuel-forecast/')[1].split('/')[0]
print(f"   Session ID: {session_id}")

if not session_id:
    print("ERROR: Could not create session")
    exit(1)

# Test each step
all_passed = True
step_names = {
    1: "Start Point",
    2: "Coal Position", 
    3: "Coal Contracts",
    4: "Use Factors",
    5: "Heat Rates",
    6: "Generation",
    7: "Other Costs",
    8: "Review & Save"
}

for step in range(1, 9):
    print(f"\n{step}. Step {step}: {step_names[step]}")
    
    # GET step page
    response = client.get(f'/fuel-forecast/{session_id}/step/{step}')
    get_ok = response.status_code == 200
    print(f"   GET: {response.status_code} {'OK' if get_ok else 'FAIL'}")
    
    if not get_ok:
        print(f"   ERROR: {response.text[:200]}")
        all_passed = False
        continue
    
    # POST step (except step 8 - just view review)
    if step < 8:
        if step == 1:
            data = {'start_mode': 'fresh', 'as_of_month': '2025-12'}
        else:
            data = {}
        
        response = client.post(
            f'/fuel-forecast/{session_id}/step/{step}', 
            data=data, 
            follow_redirects=False
        )
        post_ok = response.status_code in [200, 302, 303]
        print(f"   POST: {response.status_code} {'OK' if post_ok else 'FAIL'}")
        
        if not post_ok:
            print(f"   ERROR: {response.text[:200]}")
            all_passed = False

print("\n" + "=" * 60)
if all_passed:
    print("RESULT: ALL STEPS PASSED")
else:
    print("RESULT: SOME STEPS FAILED")
print("=" * 60)
