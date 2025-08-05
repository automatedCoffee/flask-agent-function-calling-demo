#!/usr/bin/env python3
"""
Test script to validate function calling flow before running the full application.
"""

import json
import sys
import os

# Add the current directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.agent_functions import get_customer, get_location, post_quote

def test_get_customer():
    """Test the get_customer function with various inputs."""
    print("=== Testing get_customer ===")
    
    test_cases = [
        {"company_name": "Epic"},
        {"company_name": "Acme"},
        {"company_name": "Globex"},
        {"company_name": "NonExistent Company XYZ123"}  # This should return an error, not mock data
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\nTest {i}: {params}")
        try:
            result = get_customer(params)
            print(f"Result: {json.dumps(result, indent=2)}")
            
            # Check if this is an error case
            if not result.get('success', True):
                print(f"✅ Correctly returned error for non-existent customer")
            elif result.get('success'):
                print(f"✅ Successfully found customer: {result.get('printCustomerName')}")
                
        except Exception as e:
            print(f"ERROR: {e}")

def test_get_location():
    """Test the get_location function with mock customer data."""
    print("\n=== Testing get_location ===")
    
    test_cases = [
        {"customer_oid": "mock-epic-001", "address_string": "123 Main"},
        {"customer_oid": "mock-epic-001", "address_string": "warehouse"},
        {"customer_oid": "mock-epic-001", "address_string": "research"},
        {"customer_oid": "mock-epic-001", "address_string": "NonExistent Address XYZ123"}  # Should return error
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\nTest {i}: {params}")
        try:
            result = get_location(params)
            print(f"Result: {json.dumps(result, indent=2)}")
            
            # Check if this is an error case  
            if not result.get('success', True):
                print(f"✅ Correctly returned error for non-existent location")
            elif result.get('success'):
                print(f"✅ Successfully found location: {result.get('PrintAddressString')}")
                
        except Exception as e:
            print(f"ERROR: {e}")

def test_post_quote():
    """Test the post_quote function with mock data."""
    print("\n=== Testing post_quote ===")
    
    quote_params = {
        "print_customer_name": "Epic Systems Corporation",
        "customer_oid": "mock-epic-001",
        "print_account": "Main Office",
        "print_address_string": "123 Main Street, Madison, WI 53703",
        "scheduled_date": "2024-08-10",
        "requestor": "John Smith",
        "job_name": "Network Installation",
        "pre_quote_data": "Install new network infrastructure",
        "prelim_quote": "Estimated $5000"
    }
    
    print(f"\nTest params: {json.dumps(quote_params, indent=2)}")
    try:
        result = post_quote(quote_params)
        print(f"Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    """Run all function tests."""
    print("Function Call Flow Validation Test")
    print("=" * 50)
    
    test_get_customer()
    test_get_location()
    test_post_quote()
    
    print("\n" + "=" * 50)
    print("Test completed. Check results above for any errors.")

if __name__ == "__main__":
    main() 