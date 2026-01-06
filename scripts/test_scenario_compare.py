"""Test the scenario comparison feature."""

import sys
sys.path.insert(0, ".")

import requests

BASE_URL = "http://localhost:8000"

def test_scenario_comparison():
    """Test the scenario comparison pages and API."""
    
    print("=" * 60)
    print("SCENARIO COMPARISON FEATURE TEST")
    print("=" * 60)
    
    # Test API endpoint
    print("\n1. Testing API list scenarios...")
    r = requests.get(f"{BASE_URL}/api/scenarios/")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        scenarios = r.json()
        print(f"   Found {len(scenarios)} scenarios:")
        for s in scenarios:
            print(f"     - {s['id']}: {s['name']}")
    else:
        print(f"   Error: {r.text[:200]}")
        return
    
    if len(scenarios) < 2:
        print("\n   Need at least 2 scenarios to test comparison!")
        return
    
    # Get scenario IDs
    scenario_a = scenarios[0]['id']
    scenario_b = scenarios[1]['id']
    
    # Test comparison API
    print(f"\n2. Testing API comparison ({scenario_a} vs {scenario_b})...")
    r = requests.get(f"{BASE_URL}/api/scenarios/compare/{scenario_a}/{scenario_b}")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        comparison = r.json()
        print(f"   Scenario A: {comparison['scenario_a']['name']}")
        print(f"   Scenario B: {comparison['scenario_b']['name']}")
        print(f"   Differences found: {len(comparison['differences'])}")
    else:
        print(f"   Error: {r.text[:200]}")
    
    # Test scenarios list page
    print("\n3. Testing scenarios list page...")
    r = requests.get(f"{BASE_URL}/scenarios")
    print(f"   Status: {r.status_code}")
    if r.status_code != 200:
        print(f"   Error: {r.text[:200]}")
    
    # Test comparison page
    print("\n4. Testing comparison page...")
    r = requests.get(f"{BASE_URL}/scenarios/compare?a={scenario_a}&b={scenario_b}")
    print(f"   Status: {r.status_code}")
    if r.status_code != 200:
        print(f"   Error: {r.text[:200]}")
    
    print("\n" + "=" * 60)
    print(f"TEST URLS:")
    print(f"  Scenarios list: {BASE_URL}/scenarios")
    print(f"  Compare: {BASE_URL}/scenarios/compare?a={scenario_a}&b={scenario_b}")
    print("=" * 60)


if __name__ == "__main__":
    test_scenario_comparison()
