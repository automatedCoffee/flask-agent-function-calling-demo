#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common.business_logic import post_quote_backendless

# Test payload matching the structure we're sending
test_quote_data = {
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

print("Testing POST quote function...")
print(f"Payload: {test_quote_data}")
print(f"Endpoint: data/Requests (not Orders)")
print("\n" + "="*50)

result = post_quote_backendless(test_quote_data)
print(f"\nResult: {result}") 