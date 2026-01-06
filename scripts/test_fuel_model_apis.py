"""
Test script for fuel model API endpoints.

Tests the use factors, heat rates, and coal contracts APIs to verify
they work correctly for CRUD operations.

Usage:
    python scripts/test_fuel_model_apis.py
"""

import sys
import os
import requests
import json
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# API base URL
BASE_URL = "http://localhost:8000"

# Test configuration
TEST_PLANT_ID = 1  # Kyger Creek
TEST_YEAR = 2025


def print_result(test_name: str, passed: bool, message: str = ""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {test_name}")
    if message and not passed:
        print(f"         {message}")


def test_use_factor_crud():
    """Test CRUD operations for use factors."""
    print("\n" + "=" * 60)
    print("Testing Use Factor API")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Get annual use factors (should return defaults or empty)
    try:
        response = requests.get(f"{BASE_URL}/api/use-factors/{TEST_PLANT_ID}/{TEST_YEAR}")
        if response.status_code == 200:
            data = response.json()
            print_result("GET annual use factors", True)
            passed += 1
        else:
            print_result("GET annual use factors", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET annual use factors", False, str(e))
        failed += 1
    
    # Test 2: PUT a monthly use factor
    try:
        update_data = {
            "use_factor_base": 0.85,
            "use_factor_ozone_non_scr": 0.10,
            "notes": "Test update"
        }
        response = requests.put(
            f"{BASE_URL}/api/use-factors/{TEST_PLANT_ID}/{TEST_YEAR}/6",
            json=update_data
        )
        if response.status_code == 200:
            data = response.json()
            if abs(data.get("use_factor_base", 0) - 0.85) < 0.001:
                print_result("PUT monthly use factor", True)
                passed += 1
            else:
                print_result("PUT monthly use factor", False, "Value not saved correctly")
                failed += 1
        else:
            print_result("PUT monthly use factor", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("PUT monthly use factor", False, str(e))
        failed += 1
    
    # Test 3: GET specific month
    try:
        response = requests.get(f"{BASE_URL}/api/use-factors/{TEST_PLANT_ID}/{TEST_YEAR}/6")
        if response.status_code == 200:
            data = response.json()
            if abs(data.get("use_factor_base", 0) - 0.85) < 0.001:
                print_result("GET monthly use factor", True)
                passed += 1
            else:
                print_result("GET monthly use factor", False, "Value mismatch")
                failed += 1
        else:
            print_result("GET monthly use factor", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET monthly use factor", False, str(e))
        failed += 1
    
    # Test 4: Bulk update
    try:
        bulk_data = {
            "values": [
                {"month": 5, "use_factor_base": 0.80, "use_factor_ozone_non_scr": 0.05},
                {"month": 6, "use_factor_base": 0.82, "use_factor_ozone_non_scr": 0.08},
                {"month": 7, "use_factor_base": 0.78, "use_factor_ozone_non_scr": 0.02},
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/use-factors/bulk/{TEST_PLANT_ID}/{TEST_YEAR}",
            json=bulk_data
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("updated_count") == 3:
                print_result("POST bulk use factors", True)
                passed += 1
            else:
                print_result("POST bulk use factors", False, f"Updated count: {data.get('updated_count')}")
                failed += 1
        else:
            print_result("POST bulk use factors", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("POST bulk use factors", False, str(e))
        failed += 1
    
    # Test 5: Copy to next year
    try:
        response = requests.post(
            f"{BASE_URL}/api/use-factors/copy/{TEST_PLANT_ID}/{TEST_YEAR}/{TEST_YEAR + 1}"
        )
        if response.status_code == 200:
            data = response.json()
            print_result("POST copy use factors", True)
            passed += 1
        else:
            print_result("POST copy use factors", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("POST copy use factors", False, str(e))
        failed += 1
    
    # Cleanup: Delete copied year
    try:
        response = requests.delete(f"{BASE_URL}/api/use-factors/{TEST_PLANT_ID}/{TEST_YEAR + 1}")
        if response.status_code == 200:
            print_result("DELETE year use factors (cleanup)", True)
            passed += 1
        else:
            print_result("DELETE year use factors (cleanup)", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("DELETE year use factors (cleanup)", False, str(e))
        failed += 1
    
    return passed, failed


def test_heat_rate_crud():
    """Test CRUD operations for heat rates."""
    print("\n" + "=" * 60)
    print("Testing Heat Rate API")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Get annual heat rates
    try:
        response = requests.get(f"{BASE_URL}/api/heat-rates/{TEST_PLANT_ID}/{TEST_YEAR}")
        if response.status_code == 200:
            data = response.json()
            print_result("GET annual heat rates", True)
            passed += 1
        else:
            print_result("GET annual heat rates", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET annual heat rates", False, str(e))
        failed += 1
    
    # Test 2: PUT plant-level heat rate
    try:
        update_data = {
            "baseline_heat_rate": 9850,
            "min_load_heat_rate": 10200,
            "suf_correction": 50,
            "prb_blend_adjustment": 100,
            "notes": "Test update"
        }
        response = requests.put(
            f"{BASE_URL}/api/heat-rates/{TEST_PLANT_ID}/{TEST_YEAR}/1",
            json=update_data
        )
        if response.status_code == 200:
            data = response.json()
            if abs(data.get("baseline_heat_rate", 0) - 9850) < 1:
                print_result("PUT plant-level heat rate", True)
                passed += 1
            else:
                print_result("PUT plant-level heat rate", False, "Value not saved correctly")
                failed += 1
        else:
            print_result("PUT plant-level heat rate", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("PUT plant-level heat rate", False, str(e))
        failed += 1
    
    # Test 3: PUT unit-level heat rate (unit 3)
    try:
        update_data = {
            "baseline_heat_rate": 9900,
            "min_load_heat_rate": 10300,
            "suf_correction": 60,
            "prb_blend_adjustment": 110,
        }
        response = requests.put(
            f"{BASE_URL}/api/heat-rates/{TEST_PLANT_ID}/{TEST_YEAR}/1?unit_number=3",
            json=update_data
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("unit_number") == 3:
                print_result("PUT unit-level heat rate", True)
                passed += 1
            else:
                print_result("PUT unit-level heat rate", False, "Unit number mismatch")
                failed += 1
        else:
            print_result("PUT unit-level heat rate", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("PUT unit-level heat rate", False, str(e))
        failed += 1
    
    # Test 4: GET monthly heat rate with fallback
    try:
        response = requests.get(f"{BASE_URL}/api/heat-rates/{TEST_PLANT_ID}/{TEST_YEAR}/1")
        if response.status_code == 200:
            data = response.json()
            if "source" in data:
                print_result("GET monthly heat rate with source", True)
                passed += 1
            else:
                print_result("GET monthly heat rate with source", False, "Missing source field")
                failed += 1
        else:
            print_result("GET monthly heat rate with source", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET monthly heat rate with source", False, str(e))
        failed += 1
    
    # Test 5: Bulk update
    try:
        bulk_data = {
            "values": [
                {"month": 1, "baseline_heat_rate": 9800, "suf_correction": 50, "prb_blend_adjustment": 100},
                {"month": 2, "baseline_heat_rate": 9825, "suf_correction": 50, "prb_blend_adjustment": 100},
                {"month": 3, "baseline_heat_rate": 9850, "suf_correction": 50, "prb_blend_adjustment": 100},
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/heat-rates/bulk/{TEST_PLANT_ID}/{TEST_YEAR}",
            json=bulk_data
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("updated_count") == 3:
                print_result("POST bulk heat rates", True)
                passed += 1
            else:
                print_result("POST bulk heat rates", False, f"Updated count: {data.get('updated_count')}")
                failed += 1
        else:
            print_result("POST bulk heat rates", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("POST bulk heat rates", False, str(e))
        failed += 1
    
    return passed, failed


def test_coal_contract_crud():
    """Test CRUD operations for coal contracts."""
    print("\n" + "=" * 60)
    print("Testing Coal Contract API")
    print("=" * 60)
    
    passed = 0
    failed = 0
    test_contract_id = None
    
    # Test 1: List contracts
    try:
        response = requests.get(f"{BASE_URL}/api/coal-contracts/")
        if response.status_code == 200:
            print_result("GET list contracts", True)
            passed += 1
        else:
            print_result("GET list contracts", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET list contracts", False, str(e))
        failed += 1
    
    # Test 2: Create contract
    try:
        contract_data = {
            "contract_id": "TEST-2025-001",
            "supplier": "Test Coal Company",
            "plant_id": TEST_PLANT_ID,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "annual_tons": 500000,
            "btu_per_lb": 12500,
            "coal_price_per_ton": 55.00,
            "barge_price_per_ton": 6.50,
            "coal_region": "NAPP"
        }
        response = requests.post(
            f"{BASE_URL}/api/coal-contracts/",
            json=contract_data
        )
        if response.status_code == 200:
            data = response.json()
            test_contract_id = data.get("id")
            print_result("POST create contract", True)
            passed += 1
        elif response.status_code == 400:
            # Contract ID already exists - try to find it
            response = requests.get(f"{BASE_URL}/api/coal-contracts/")
            if response.status_code == 200:
                contracts = response.json()
                for c in contracts:
                    if c.get("contract_id") == "TEST-2025-001":
                        test_contract_id = c.get("id")
                        break
            print_result("POST create contract (exists)", True)
            passed += 1
        else:
            print_result("POST create contract", False, f"Status: {response.status_code}, {response.text}")
            failed += 1
    except Exception as e:
        print_result("POST create contract", False, str(e))
        failed += 1
    
    if test_contract_id:
        # Test 3: Get specific contract
        try:
            response = requests.get(f"{BASE_URL}/api/coal-contracts/{test_contract_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get("supplier") == "Test Coal Company":
                    print_result("GET specific contract", True)
                    passed += 1
                else:
                    print_result("GET specific contract", False, "Data mismatch")
                    failed += 1
            else:
                print_result("GET specific contract", False, f"Status: {response.status_code}")
                failed += 1
        except Exception as e:
            print_result("GET specific contract", False, str(e))
            failed += 1
        
        # Test 4: Update contract
        try:
            update_data = {
                "coal_price_per_ton": 58.00,
                "annual_tons": 520000
            }
            response = requests.put(
                f"{BASE_URL}/api/coal-contracts/{test_contract_id}",
                json=update_data
            )
            if response.status_code == 200:
                data = response.json()
                if abs(data.get("coal_price_per_ton", 0) - 58.00) < 0.01:
                    print_result("PUT update contract", True)
                    passed += 1
                else:
                    print_result("PUT update contract", False, "Value not updated")
                    failed += 1
            else:
                print_result("PUT update contract", False, f"Status: {response.status_code}")
                failed += 1
        except Exception as e:
            print_result("PUT update contract", False, str(e))
            failed += 1
        
        # Test 5: Add pricing schedule
        try:
            pricing_data = {
                "effective_month": "202506",
                "coal_price_per_ton": 56.50,
                "barge_price_per_ton": 7.00,
                "btu_per_lb": 12600
            }
            response = requests.put(
                f"{BASE_URL}/api/coal-contracts/{test_contract_id}/pricing/202506",
                json=pricing_data
            )
            if response.status_code == 200:
                print_result("PUT contract pricing", True)
                passed += 1
            else:
                print_result("PUT contract pricing", False, f"Status: {response.status_code}")
                failed += 1
        except Exception as e:
            print_result("PUT contract pricing", False, str(e))
            failed += 1
        
        # Test 6: Get pricing schedule
        try:
            response = requests.get(f"{BASE_URL}/api/coal-contracts/{test_contract_id}/pricing")
            if response.status_code == 200:
                data = response.json()
                print_result("GET contract pricing", True)
                passed += 1
            else:
                print_result("GET contract pricing", False, f"Status: {response.status_code}")
                failed += 1
        except Exception as e:
            print_result("GET contract pricing", False, str(e))
            failed += 1
        
        # Cleanup: Delete test contract
        try:
            response = requests.delete(f"{BASE_URL}/api/coal-contracts/{test_contract_id}")
            if response.status_code == 200:
                print_result("DELETE contract (cleanup)", True)
                passed += 1
            else:
                print_result("DELETE contract (cleanup)", False, f"Status: {response.status_code}")
                failed += 1
        except Exception as e:
            print_result("DELETE contract (cleanup)", False, str(e))
            failed += 1
    else:
        print_result("Skipped contract tests (no test contract ID)", False, "Contract not created")
        failed += 4
    
    return passed, failed


def test_uncommitted_pricing():
    """Test uncommitted coal pricing endpoints."""
    print("\n" + "=" * 60)
    print("Testing Uncommitted Coal Pricing API")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 1: Get uncommitted prices
    try:
        response = requests.get(f"{BASE_URL}/api/coal-contracts/uncommitted/{TEST_PLANT_ID}/{TEST_YEAR}")
        if response.status_code == 200:
            print_result("GET uncommitted prices", True)
            passed += 1
        else:
            print_result("GET uncommitted prices", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET uncommitted prices", False, str(e))
        failed += 1
    
    # Test 2: Update uncommitted price
    try:
        update_data = {
            "price_per_ton": 52.00,
            "barge_per_ton": 6.00,
            "btu_per_lb": 12400,
            "source_name": "NAPP Spot"
        }
        response = requests.put(
            f"{BASE_URL}/api/coal-contracts/uncommitted/{TEST_PLANT_ID}/{TEST_YEAR}/6",
            json=update_data
        )
        if response.status_code == 200:
            data = response.json()
            if abs(data.get("price_per_ton", 0) - 52.00) < 0.01:
                print_result("PUT uncommitted price", True)
                passed += 1
            else:
                print_result("PUT uncommitted price", False, "Value mismatch")
                failed += 1
        else:
            print_result("PUT uncommitted price", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("PUT uncommitted price", False, str(e))
        failed += 1
    
    # Test 3: Get coal supply breakdown
    try:
        response = requests.get(f"{BASE_URL}/api/coal-contracts/supply/{TEST_PLANT_ID}/{TEST_YEAR}/6")
        if response.status_code == 200:
            data = response.json()
            if "contracted" in data and "uncommitted" in data:
                print_result("GET coal supply breakdown", True)
                passed += 1
            else:
                print_result("GET coal supply breakdown", False, "Missing expected fields")
                failed += 1
        else:
            print_result("GET coal supply breakdown", False, f"Status: {response.status_code}")
            failed += 1
    except Exception as e:
        print_result("GET coal supply breakdown", False, str(e))
        failed += 1
    
    return passed, failed


def main():
    """Run all API tests."""
    print("\n" + "=" * 60)
    print("FUEL MODEL API TESTS")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Plant ID: {TEST_PLANT_ID}")
    print(f"Test Year: {TEST_YEAR}")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print("\nServer is running.")
    except:
        print("\n[ERROR] Cannot connect to server at", BASE_URL)
        print("Make sure the server is running:")
        print("  python -m uvicorn src.api.main:app --reload")
        return
    
    total_passed = 0
    total_failed = 0
    
    # Run tests
    p, f = test_use_factor_crud()
    total_passed += p
    total_failed += f
    
    p, f = test_heat_rate_crud()
    total_passed += p
    total_failed += f
    
    p, f = test_coal_contract_crud()
    total_passed += p
    total_failed += f
    
    p, f = test_uncommitted_pricing()
    total_passed += p
    total_failed += f
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Total:  {total_passed + total_failed}")
    
    if total_failed == 0:
        print("\n  All tests passed!")
    else:
        print(f"\n  {total_failed} test(s) failed.")
    
    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

