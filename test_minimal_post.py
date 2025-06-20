#!/usr/bin/env python3

import requests
import json
import os

# Use the same credentials as the working GET requests
BACKENDLESS_API_URL = 'https://api.backendless.com'
BACKENDLESS_APP_ID = '0C12C4C1-B47E-AF0E-FF2E-B6014104EC00'  
BACKENDLESS_API_KEY = 'D8927048-37D8-4EDD-9FF4-C0DA8D68E279'

# Minimal test payload - just the absolutely essential fields
minimal_payload = {
    "Status": "PRE-ESTIMATE",
    "CustomerOid": "9493B230-DDA6-4EE0-816E-4DEEE9CE012C"
}

print("Testing minimal POST to Orders table...")
print(f"Payload: {json.dumps(minimal_payload, indent=2)}")

# Build URL same as GET requests
api_url = f"{BACKENDLESS_API_URL}/{BACKENDLESS_APP_ID}/{BACKENDLESS_API_KEY}/data/Requests"
print(f"URL: {api_url}")

try:
    response = requests.post(api_url, json=minimal_payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code in [200, 201]:
        print("SUCCESS! Minimal payload worked")
        result = response.json()
        print(f"Created record with ID: {result.get('objectId')}")
    else:
        print(f"FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "="*50)
print("Now testing your full payload...")

# Your full payload
full_payload = {
    "Status": "PRE-ESTIMATE",
    "printCustomerName": "Epic Construction",
    "CustomerOid": "9493B230-DDA6-4EE0-816E-4DEEE9CE012C",
    "printAccount": "Unknown Account",
    "PrintAddressString": "Meadowlands Racetrack / 1 Racetrack Drive East Rutherford, New Jersey",
    "scheduleddate": "2025-06-22",
    "Requestor": "Epic Construction",
    "pre_quote_data": "Scope of work is to power wash all patio areas, fence surfaces, and vestibule areas.",
    "JobName": "Patio power wash",
    "prelim_quote": "Quote details to be determined"
}

try:
    response = requests.post(api_url, json=full_payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code in [200, 201]:
        print("SUCCESS! Full payload worked")
        result = response.json()
        print(f"Created record with ID: {result.get('objectId')}")
    else:
        print(f"FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}") 