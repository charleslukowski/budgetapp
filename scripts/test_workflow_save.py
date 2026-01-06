"""Test the complete workflow: create forecast -> save -> compare."""

import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from src.api.main import app
from datetime import datetime

client = TestClient(app, raise_server_exceptions=True)

def test_workflow_to_save():
    """Test creating a forecast through the workflow and saving it as a scenario."""
    
    print("=" * 60)
    print("WORKFLOW -> SAVE -> COMPARE TEST")
    print("=" * 60)
    
    # Step 1: Start new workflow
    print("\n1. Creating new workflow session...")
    response = client.get('/fuel-forecast/new', follow_redirects=False)
    location = response.headers.get('location', '')
    session_id = location.split('/fuel-forecast/')[1].split('/')[0]
    print(f"   Session ID: {session_id}")
    
    # Step 2: Complete workflow steps 1-7
    print("\n2. Completing workflow steps 1-7...")
    
    # Step 1: Start with fresh scenario
    client.post(f'/fuel-forecast/{session_id}/step/1', 
                data={'start_mode': 'fresh', 'as_of_month': '2025-12'})
    
    # Steps 2-7: Use defaults
    for step in range(2, 8):
        client.post(f'/fuel-forecast/{session_id}/step/{step}', data={})
    print("   Completed steps 1-7")
    
    # Step 3: Calculate and save (Step 8)
    print("\n3. Calculating forecast and saving as scenario...")
    scenario_name = f"Test Workflow Scenario {datetime.now().strftime('%H%M%S')}"
    response = client.post(
        f'/fuel-forecast/{session_id}/step/8',
        data={
            'action': 'save',
            'scenario_name': scenario_name,
            'notes': 'Created via automated test'
        }
    )
    print(f"   Save status: {response.status_code}")
    
    # Step 4: Verify scenario appears in list
    print("\n4. Checking scenario list...")
    response = client.get('/api/scenarios/')
    scenarios = response.json()
    
    found = False
    saved_id = None
    for s in scenarios:
        if s['name'] == scenario_name:
            found = True
            saved_id = s['id']
            print(f"   Found saved scenario: {s['name']} (ID: {s['id']})")
            print(f"   Has snapshot: {s['has_snapshot']}")
            break
    
    if not found:
        print("   ERROR: Saved scenario not found in list!")
        return False
    
    # Step 5: Test comparison with another scenario
    print("\n5. Testing comparison with existing scenario...")
    if len(scenarios) >= 2:
        other_id = None
        for s in scenarios:
            if s['id'] != saved_id and s['has_snapshot']:
                other_id = s['id']
                break
        
        if other_id:
            response = client.get(f'/scenarios/compare?a={saved_id}&b={other_id}')
            print(f"   Comparison page status: {response.status_code}")
            if response.status_code == 200:
                print("   SUCCESS: Workflow scenario can be compared!")
            else:
                print(f"   ERROR: {response.text[:200]}")
        else:
            print("   No other scenario with snapshot to compare with")
    else:
        print("   Only one scenario exists, skipping comparison test")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print(f"Scenario URL: http://localhost:8000/scenarios")
    print(f"Compare URL: http://localhost:8000/scenarios/compare?a={saved_id}&b=3")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    test_workflow_to_save()
