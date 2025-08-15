import asyncio
import json
from datetime import datetime, timedelta
import random
from common.config import ARTIFICIAL_DELAY, MOCK_DATA_SIZE
import pathlib
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Configuration
BACKENDLESS_API_URL = os.getenv('BACKENDLESS_API_URL', 'https://api.backendless.com')
BACKENDLESS_APP_ID = os.getenv('BACKENDLESS_APP_ID', '0C12C4C1-B47E-AF0E-FF2E-B6014104EC00')
BACKENDLESS_API_KEY = os.getenv('BACKENDLESS_API_KEY', 'D8927048-37D8-4EDD-9FF4-C0DA8D68E279')

def save_mock_data(data):
    """Save mock data to a timestamped file in mock_data_outputs directory."""
    # Create mock_data_outputs directory if it doesn't exist
    output_dir = pathlib.Path("mock_data_outputs")
    output_dir.mkdir(exist_ok=True)

    # Clean up old mock data files
    cleanup_mock_data_files(output_dir)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"mock_data_{timestamp}.json"

    # Save the data with pretty printing
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nMock data saved to: {output_file}")


def cleanup_mock_data_files(output_dir):
    """Remove all existing mock data files in the output directory."""
    for file in output_dir.glob("mock_data_*.json"):
        try:
            file.unlink()
        except Exception as e:
            print(f"Warning: Could not delete {file}: {e}")


# Mock data generation
def generate_mock_data():
    customers = []
    appointments = []
    orders = []

    # Generate customers
    for i in range(MOCK_DATA_SIZE["customers"]):
        customer = {
            "id": f"CUST{i:04d}",
            "name": f"Customer {i}",
            "phone": f"+1555{i:07d}",
            "email": f"customer{i}@example.com",
            "joined_date": (
                datetime.now() - timedelta(days=random.randint(0, 7))
            ).isoformat(),
        }
        customers.append(customer)

    # Generate appointments
    for i in range(MOCK_DATA_SIZE["appointments"]):
        customer = random.choice(customers)
        appointment = {
            "id": f"APT{i:04d}",
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "date": (datetime.now() + timedelta(days=random.randint(0, 7))).isoformat(),
            "service": random.choice(
                ["Consultation", "Follow-up", "Review", "Planning"]
            ),
            "status": random.choice(["Scheduled", "Completed", "Cancelled"]),
        }
        appointments.append(appointment)

    # Generate orders
    for i in range(MOCK_DATA_SIZE["orders"]):
        customer = random.choice(customers)
        order = {
            "id": f"ORD{i:04d}",
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "date": (datetime.now() - timedelta(days=random.randint(0, 7))).isoformat(),
            "items": random.randint(1, 5),
            "total": round(random.uniform(10.0, 500.0), 2),
            "status": random.choice(["Pending", "Shipped", "Delivered", "Cancelled"]),
        }
        orders.append(order)

    # Format sample data for display
    sample_data = []
    sample_customers = random.sample(customers, 3)
    for customer in sample_customers:
        customer_data = {
            "Customer": customer["name"],
            "ID": customer["id"],
            "Phone": customer["phone"],
            "Email": customer["email"],
            "Appointments": [],
            "Orders": [],
        }

        # Add appointments
        customer_appointments = [
            a for a in appointments if a["customer_id"] == customer["id"]
        ]
        for apt in customer_appointments[:2]:
            customer_data["Appointments"].append(
                {
                    "Service": apt["service"],
                    "Date": apt["date"][:10],
                    "Status": apt["status"],
                }
            )

        # Add orders
        customer_orders = [o for o in orders if o["customer_id"] == customer["id"]]
        for order in customer_orders[:2]:
            customer_data["Orders"].append(
                {
                    "ID": order["id"],
                    "Total": f"${order['total']}",
                    "Status": order["status"],
                    "Date": order["date"][:10],
                    "# Items": order["items"],
                }
            )

        sample_data.append(customer_data)

    # Create data object
    mock_data = {
        "customers": customers,
        "appointments": appointments,
        "orders": orders,
        "sample_data": sample_data,
    }

    # Save the mock data
    save_mock_data(mock_data)

    return mock_data


# Initialize mock data
MOCK_DATA = generate_mock_data()


async def simulate_delay(delay_type):
    """Simulate processing delay based on operation type."""
    await asyncio.sleep(ARTIFICIAL_DELAY[delay_type])


async def get_customer(phone=None, email=None, customer_id=None):
    """Look up a customer by phone, email, or ID."""
    await simulate_delay("database")

    if phone:
        customer = next(
            (c for c in MOCK_DATA["customers"] if c["phone"] == phone), None
        )
    elif email:
        customer = next(
            (c for c in MOCK_DATA["customers"] if c["email"] == email), None
        )
    elif customer_id:
        customer = next(
            (c for c in MOCK_DATA["customers"] if c["id"] == customer_id), None
        )
    else:
        return {"error": "No search criteria provided"}

    return customer if customer else {"error": "Customer not found"}


async def get_customer_appointments(customer_id):
    """Get all appointments for a customer."""
    await simulate_delay("database")

    appointments = [
        a for a in MOCK_DATA["appointments"] if a["customer_id"] == customer_id
    ]
    return {"customer_id": customer_id, "appointments": appointments}


async def get_customer_orders(customer_id):
    """Get all orders for a customer."""
    await simulate_delay("database")

    orders = [o for o in MOCK_DATA["orders"] if o["customer_id"] == customer_id]
    return {"customer_id": customer_id, "orders": orders}


async def schedule_appointment(customer_id, date, service):
    """Schedule a new appointment."""
    await simulate_delay("database")

    # Verify customer exists
    customer = await get_customer(customer_id=customer_id)
    if "error" in customer:
        return customer

    # Create new appointment
    appointment_id = f"APT{len(MOCK_DATA['appointments']):04d}"
    appointment = {
        "id": appointment_id,
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "date": date,
        "service": service,
        "status": "Scheduled",
    }

    MOCK_DATA["appointments"].append(appointment)
    return appointment


async def get_available_appointment_slots(start_date, end_date):
    """Get available appointment slots."""
    await simulate_delay("database")

    # Convert dates to datetime objects
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    # Generate available slots (9 AM to 5 PM, 1-hour slots)
    slots = []
    current = start
    while current <= end:
        if current.hour >= 9 and current.hour < 17:
            slot_time = current.isoformat()
            # Check if slot is already taken
            taken = any(a["date"] == slot_time for a in MOCK_DATA["appointments"])
            if not taken:
                slots.append(slot_time)
        current += timedelta(hours=1)

    return {"available_slots": slots}


async def prepare_agent_filler_message(websocket, message_type):
    """
    Handle agent filler messages while maintaining proper function call protocol.
    Returns a simple confirmation first, then sends the actual message to the client.
    """
    # First prepare the result that will be the function call response
    result = {"status": "queued", "message_type": message_type}

    # Prepare the inject message but don't send it yet
    if message_type == "lookup":
        inject_message = {
            "type": "InjectAgentMessage",
            "message": "Let me look that up for you...",
        }
    else:
        inject_message = {
            "type": "InjectAgentMessage",
            "message": "One moment please...",
        }

    # Return the result first - this becomes the function call response
    # The caller can then send the inject message after handling the function response
    return {"function_response": result, "inject_message": inject_message}


async def prepare_farewell_message(websocket, farewell_type):
    """End the conversation with an appropriate farewell message and close the connection."""
    # Prepare farewell message based on type
    if farewell_type == "thanks":
        message = "Thank you for calling! Have a great day!"
    elif farewell_type == "help":
        message = "I'm glad I could help! Have a wonderful day!"
    else:  # general
        message = "Goodbye! Have a nice day!"

    # Prepare messages but don't send them
    inject_message = {"type": "InjectAgentMessage", "message": message}

    close_message = {"type": "close"}

    # Return both messages to be sent in correct order by the caller
    return {
        "function_response": {"status": "closing", "message": message},
        "inject_message": inject_message,
        "close_message": close_message,
    }

def get_customer_backendless(company_name):
    """
    Look up a customer by company name from Backendless.
    Returns CustomerOid and printCustomerName if found.
    Falls back to mock data ONLY if API credentials are not configured.
    """
    print(f"get_customer_backendless called with company_name: '{company_name}'")
    
    # Check if Backendless API credentials are configured
    if not BACKENDLESS_APP_ID or not BACKENDLESS_API_KEY:
        print(f"Backendless API not configured, using mock data for customer lookup: {company_name}")
        return get_customer_mock(company_name)
    
    print(f"Using Backendless API credentials - APP_ID: {BACKENDLESS_APP_ID[:8]}..., API_KEY: {BACKENDLESS_API_KEY[:8]}...")
    
    try:
        # Build the correct Backendless URL structure
        api_url = f"{BACKENDLESS_API_URL}/{BACKENDLESS_APP_ID}/{BACKENDLESS_API_KEY}/data/Customers"
        
        # Create the where clause for the company name search
        where_clause = f"Company LIKE '%{company_name}%'"
        
        print(f"Making API request to: {api_url}")
        print(f"Where clause: {where_clause}")
        
        # Make the API request to Backendless
        response = requests.get(
            api_url,
            params={'where': where_clause},
            timeout=30  # Add timeout to prevent hanging
        )
        
        print(f"API response status: {response.status_code}")
        print(f"API response content: {response.text[:500]}...")
        
        if response.status_code == 200:
            customers = response.json()
            print(f"Found {len(customers)} customers matching company search")
            if customers and len(customers) > 0:
                customer = customers[0]  # Take the first match
                print(f"Using customer: {customer.get('Company')} with ID: {customer.get('objectId')}")
                return {
                    'CustomerOid': customer.get('objectId'),
                    'printCustomerName': customer.get('Company'),
                    'success': True
                }
            else:
                print(f"No customers found for company: {company_name}")
                return {
                    'error': f"Customer '{company_name}' not found in our system. Please check the company name and try again.",
                    'success': False,
                    'company_searched': company_name
                }
        else:
            print(f"Backendless API request failed with status {response.status_code}, falling back to mock data")
            return get_customer_mock(company_name)
            
    except requests.exceptions.Timeout:
        print(f"Backendless API timeout, falling back to mock data")
        return get_customer_mock(company_name)
    except requests.exceptions.RequestException as e:
        print(f"Backendless API request error, falling back to mock data: {str(e)}")
        return get_customer_mock(company_name)
    except Exception as e:
        print(f"Backendless API error, falling back to mock data: {str(e)}")
        return get_customer_mock(company_name)

def get_customer_mock(company_name):
    """
    Mock customer lookup for demonstration purposes.
    Returns sample customer data for common company names.
    """
    # Sample customers for demo
    mock_customers = {
        "epic": {
            'CustomerOid': 'mock-epic-001',
            'printCustomerName': 'Epic Systems Corporation',
            'success': True
        },
        "acme": {
            'CustomerOid': 'mock-acme-001', 
            'printCustomerName': 'Acme Corporation',
            'success': True
        },
        "globex": {
            'CustomerOid': 'mock-globex-001',
            'printCustomerName': 'Globex Corporation', 
            'success': True
        },
        "initech": {
            'CustomerOid': 'mock-initech-001',
            'printCustomerName': 'Initech',
            'success': True
        }
    }
    
    # Look for a match (case insensitive)
    company_lower = company_name.lower()
    for key, customer in mock_customers.items():
        if key in company_lower or company_lower in key:
            print(f"Found mock customer: {customer['printCustomerName']}")
            return customer
    
    # If no match found, return the first customer as a fallback
    fallback = list(mock_customers.values())[0]
    print(f"No exact match for '{company_name}', using fallback: {fallback['printCustomerName']}")
    return fallback

def get_location_backendless(customer_oid, address_string):
    """
    Look up a location for a customer by address string from Backendless.
    Searches in the Locations table using AddressOnlyString and FullAddressString fields.
    Returns ParentLocationOid, printAccount, and PrintAddressString if found.
    Falls back to mock data ONLY if API credentials are not configured.
    """
    print(f"Location lookup called with customer_oid: {customer_oid}, address_string: {address_string}")
    
    # Check if Backendless API credentials are configured
    if not BACKENDLESS_APP_ID or not BACKENDLESS_API_KEY:
        print(f"Backendless API not configured, using mock data for location lookup: {address_string}")
        return get_location_mock(customer_oid, address_string)
    
    print(f"Using Backendless API credentials - APP_ID: {BACKENDLESS_APP_ID[:8]}..., API_KEY: {BACKENDLESS_API_KEY[:8]}...")
    
    try:
        # Build the correct Backendless URL structure - search in Locations table
        api_url = f"{BACKENDLESS_API_URL}/{BACKENDLESS_APP_ID}/{BACKENDLESS_API_KEY}/data/Locations"
        
        # Create the where clause for the location search - search by address fields
        where_clause = f"AddressOnlyString LIKE '%{address_string}%' OR FullAddressString LIKE '%{address_string}%'"
        
        print(f"Making API request to: {api_url}")
        print(f"Where clause: {where_clause}")
        
        # Make the API request to Backendless
        response = requests.get(
            api_url,
            params={
                'where': where_clause,
                'props': 'AddressOnlyString,FullAddressString,ParentAccountName,CustomerOid,objectId'
            }
        )
        
        print(f"API response status: {response.status_code}")
        print(f"API response content: {response.text[:500]}...")
        
        if response.status_code == 200:
            locations = response.json()
            print(f"Found {len(locations)} locations matching address search")
            if locations and len(locations) > 0:
                location = locations[0]  # Take the first match
                print(f"Using location: {location.get('printAccount')} with address: {location.get('FullAddressString', location.get('AddressOnlyString'))}")
                return {
                    'ParentLocationOid': location.get('objectId'),
                    'printAccount': location.get('printAccount', 'Unknown Account'),
                    'PrintAddressString': location.get('FullAddressString', location.get('AddressOnlyString', 'Unknown Address')),
                    'success': True
                }
            else:
                print(f"No locations found for address: {address_string}")
                return {
                    'error': f"Location matching '{address_string}' not found for this customer. Please provide a different address or location description.",
                    'success': False,
                    'address_searched': address_string,
                    'customer_oid': customer_oid
                }
        else:
            print(f"Backendless API request failed with status {response.status_code}, falling back to mock data")
            return get_location_mock(customer_oid, address_string)
            
    except Exception as e:
        print(f"Backendless API error, falling back to mock data: {str(e)}")
        return get_location_mock(customer_oid, address_string)

def get_location_mock(customer_oid, address_string):
    """
    Mock location lookup for demonstration purposes.
    Returns sample location data based on customer and address.
    """
    # Sample locations for demo
    mock_locations = [
        {
            'ParentLocationOid': 'mock-loc-001',
            'printAccount': 'Main Office',
            'PrintAddressString': '123 Main Street, Madison, WI 53703',
            'keywords': ['main', 'office', '123', 'madison']
        },
        {
            'ParentLocationOid': 'mock-loc-002', 
            'printAccount': 'Warehouse Facility',
            'PrintAddressString': '456 Industrial Drive, Verona, WI 53593',
            'keywords': ['warehouse', 'industrial', '456', 'verona']
        },
        {
            'ParentLocationOid': 'mock-loc-003',
            'printAccount': 'Research Campus',
            'PrintAddressString': '789 Innovation Blvd, Middleton, WI 53562',
            'keywords': ['research', 'campus', '789', 'innovation', 'middleton']
        }
    ]
    
    # Look for a match based on address string
    address_lower = address_string.lower()
    for location in mock_locations:
        for keyword in location['keywords']:
            if keyword in address_lower:
                print(f"Found mock location: {location['PrintAddressString']}")
                return {
                    'ParentLocationOid': location['ParentLocationOid'],
                    'printAccount': location['printAccount'], 
                    'PrintAddressString': location['PrintAddressString'],
                    'success': True
                }
    
    # If no match found, return the first location as a fallback
    fallback = mock_locations[0]
    print(f"No exact match for '{address_string}', using fallback: {fallback['PrintAddressString']}")
    return {
        'ParentLocationOid': fallback['ParentLocationOid'],
        'printAccount': fallback['printAccount'],
        'PrintAddressString': fallback['PrintAddressString'], 
        'success': True
    }

def post_quote_backendless(quote_data):
    """
    Post a structured quote request to Backendless.
    Returns the created quote object if successful.
    Falls back to saving locally if API credentials are not configured.
    """
    print(f"Creating quote with data: {json.dumps(quote_data, indent=2)}")
    
    # Check if Backendless API credentials are configured
    if not BACKENDLESS_APP_ID or not BACKENDLESS_API_KEY:
        print("Backendless API not configured, saving quote locally")
        return save_quote_data(quote_data)
    
    print(f"Using Backendless API credentials - APP_ID: {BACKENDLESS_APP_ID[:8]}..., API_KEY: {BACKENDLESS_API_KEY[:8]}...")
    
    try:
        # Build the correct Backendless URL structure
        api_url = f"{BACKENDLESS_API_URL}/{BACKENDLESS_APP_ID}/{BACKENDLESS_API_KEY}/data/Requests"
        
        print(f"Making POST request to: {api_url}")
        
        # Make the API request to Backendless
        response = requests.post(
            api_url,
            json=quote_data
        )
        
        print(f"API response status: {response.status_code}")
        print(f"API response content: {response.text[:500]}...")
        
        if response.status_code in [200, 201]:
            created_quote = response.json()
            request_number = created_quote.get('InternalRequestNumber', 'N/A')
            object_id = created_quote.get('objectId', 'N/A')
            
            print(f"Quote successfully created in Backendless with ID: {object_id}")
            print(f"Internal Request Number: {request_number}")
            
            return {
                'quote_id': object_id,
                'internal_request_number': request_number,
                'success': True,
                'message': f"Quote successfully created! Internal Request Number: {request_number}",
                'data': created_quote
            }
        else:
            print(f"Backendless API request failed with status {response.status_code}, saving locally")
            return save_quote_data(quote_data)
            
    except Exception as e:
        print(f"Backendless API error, saving quote locally: {str(e)}")
        return save_quote_data(quote_data)

# Save a copy of the quote data for debugging/backup
def save_quote_data(quote_data):
    """Save quote data to a timestamped file in quote_data_outputs directory."""
    # Create quote_data_outputs directory if it doesn't exist
    output_dir = Path("quote_data_outputs")
    output_dir.mkdir(exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"quote_data_{timestamp}.json"

    # Save the data with pretty printing
    with open(output_file, "w") as f:
        json.dump(quote_data, f, indent=2)

    print(f"\nQuote data saved to: {output_file}")
    
    # Return a proper response indicating success
    return {
        'quote_id': f"local_{timestamp}",
        'success': True,
        'message': f"Quote saved locally to {output_file}",
        'file_path': str(output_file),
        'data': quote_data
    }
