import json
import requests

from .business_logic import (
    get_customer_backendless,
    get_location_backendless,
    post_quote_backendless
)

def get_customer(params):
    """Look up a customer by company name from Backendless."""
    company_name = params.get("company_name")
    if not company_name:
        return {"error": "Company name is required."}
    
    result = get_customer_backendless(company_name)
    return result

def get_location(params):
    """Look up a location for a customer by address string from Backendless."""
    customer_oid = params.get("customer_oid")
    address_string = params.get("address_string")
    if not customer_oid or not address_string:
        return {"error": "Customer OID and address string are required."}
    
    result = get_location_backendless(customer_oid, address_string)
    return result

def post_quote(params):
    """Post a structured quote request to Backendless."""
    # Extract individual parameters instead of expecting a nested quote_data object
    status = params.get("status", "PRE-ESTIMATE")
    print_customer_name = params.get("print_customer_name")
    customer_oid = params.get("customer_oid")
    print_account = params.get("print_account")
    print_address_string = params.get("print_address_string")
    scheduled_date = params.get("scheduled_date")
    requestor = params.get("requestor")
    pre_quote_data = params.get("pre_quote_data")
    job_name = params.get("job_name")
    prelim_quote = params.get("prelim_quote")
    
    # Validate required fields
    required_fields = {
        "print_customer_name": print_customer_name,
        "customer_oid": customer_oid,
        "print_account": print_account,
        "print_address_string": print_address_string,
        "scheduled_date": scheduled_date,
        "requestor": requestor,
        "job_name": job_name
    }
    
    missing_fields = [field for field, value in required_fields.items() if not value]
    if missing_fields:
        return {"error": f"Missing required fields: {', '.join(missing_fields)}"}
    
    # Structure the payload according to the user's specifications
    quote_data = {
        "Status": status,
        "printCustomerName": print_customer_name,
        "CustomerOid": customer_oid,
        "printAccount": print_account,
        "PrintAddressString": print_address_string,
        "scheduleddate": scheduled_date,
        "Requestor": requestor,
        "pre_quote_data": pre_quote_data or "No additional details provided",
        "JobName": job_name,
        "prelim_quote": prelim_quote or "Quote details to be determined"
    }
    
    result = post_quote_backendless(quote_data)
    return result

# Function definitions that will be sent to the Voice Agent API
FUNCTION_DEFINITIONS = [
    {
        "name": "get_customer",
        "description": "Retrieve customer information from the ERP system based on the company name. Use this function to get the CustomerOid and printCustomerName for a quote.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The company name of the customer to look up. Example: 'Acme Corp'"
                }
            },
            "required": ["company_name"]
        },
        "client_side": False
    },
    {
        "name": "get_location",
        "description": "Retrieve a specific job location for a customer from the ERP system based on their CustomerOid and a partial address string. Use this function to get ParentLocationOid, printAccount, and PrintAddressString.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_oid": {
                    "type": "string",
                    "description": "The unique identifier (objectId) of the customer, obtained from the get_customer function."
                },
                "address_string": {
                    "type": "string",
                    "description": "A part of the address string to identify the job location. Example: '123 Main St' or 'Suite 400'"
                }
            },
            "required": ["customer_oid", "address_string"]
        },
        "client_side": False
    },
    {
        "name": "post_quote",
        "description": "Submit a complete structured quote request to the ERP system. This function should only be called once all required information has been collected from the customer and confirmed. The customer data should come from get_customer function, and location data should come from get_location function. Upon successful creation, the function will return an Internal Request Number that should be shared with the customer for confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "The status of the quote. Default is 'PRE-ESTIMATE'.",
                    "default": "PRE-ESTIMATE"
                },
                "print_customer_name": {
                    "type": "string",
                    "description": "The customer company name from get_customer function result (customers.company field)."
                },
                "customer_oid": {
                    "type": "string",
                    "description": "The customer object ID from get_customer function result (customers.objectId field)."
                },
                "print_account": {
                    "type": "string",
                    "description": "The account name from get_location function result (locations.ParentAccountName field)."
                },
                "print_address_string": {
                    "type": "string",
                    "description": "The address string from get_location function result (locations.addressonlystring field)."
                },
                "scheduled_date": {
                    "type": "string",
                    "description": "The date of service provided by the user (userInput). Format: YYYY-MM-DD or user's preferred format."
                },
                "requestor": {
                    "type": "string",
                    "description": "The customer job contact name provided by the user (userInput)."
                },
                "pre_quote_data": {
                    "type": "string",
                    "description": "Scope of work and extra information provided by the user (userInput). Optional field."
                },
                "job_name": {
                    "type": "string",
                    "description": "The name of the job provided by the user (userInput)."
                },
                "prelim_quote": {
                    "type": "string",
                    "description": "Free form text field to store quote information provided by the user (userInput). Optional field."
                }
            },
            "required": [
                "print_customer_name", "customer_oid", "print_account", 
                "print_address_string", "scheduled_date", "requestor", "job_name"
            ]
        },
        "client_side": False
    }
]

# Map function names to their implementations
FUNCTION_MAP = {
    "get_customer": get_customer,
    "get_location": get_location,
    "post_quote": post_quote,
}
