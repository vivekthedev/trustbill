import json
import os
import re

import boto3

# Initialize DynamoDB resources (lazy-loaded to support testing)
VENDORS_TABLE = os.getenv("TrustedVendorsTable")
INVOICES_TABLE = os.getenv("InvoicesTable")
dynamodb = boto3.resource("dynamodb")

def get_tables():
    """Get DynamoDB tables. Lazy loading to support testing."""
    return {
        "vendors": dynamodb.Table(VENDORS_TABLE),
        "invoices": dynamodb.Table(INVOICES_TABLE)
    }


def get_all_data():
    """Get all vendors and invoices data"""
    tables = get_tables()
    # Get all vendors
    vendor_response = tables["vendors"].scan()
    vendors = vendor_response.get("Items", [])    # Get all invoices
    invoice_response = tables["invoices"].scan()
    invoices = invoice_response.get("Items", [])

    # Combine the data
    return {"vendors": vendors, "invoices": invoices}


def unflag_invoice(invoice_id):
    """Remove flags from a specific invoice"""
    tables = get_tables()
    try:
        response = tables["invoices"].get_item(Key={"invoiceId": invoice_id})

        if "Item" not in response:
            return {
                "success": False,
                "message": f"Invoice with ID {invoice_id} not found",
            }
        invoice = response["Item"]
        flags = invoice.get("Flags", {})
        
        for k, v in flags.items():
            flags[k] = False

        tables["invoices"].put_item(Item=invoice)

        return {
            "success": True,
            "message": f"Invoice {invoice_id} has been unflagged",
            "invoice": invoice,
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


def lambda_handler(event, context):
    """Handle API Gateway requests"""
    # Extract path and method from the event
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Add CORS headers for browser requests
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
    }

    # Handle OPTIONS request for CORS preflight
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": json.dumps({})}

    # Handle GET /all request
    if http_method == "GET" and path == "/invoices":
        data = get_all_data()
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(data, default=str),
        }

    # Handle PUT /invoices/{invoiceId} request
    if http_method == "PUT" and (resource == "/invoices/{invoiceId}"):
        invoice_id = event.get("pathParameters", {}).get("invoiceId", "")
        if invoice_id:
            result = unflag_invoice(invoice_id)
            status_code = 200 if result["success"] else 404
            return {
                "statusCode": status_code,
                "headers": headers,
                "body": json.dumps(result, default=str),
            }
        else:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"message": "invoiceId is required"}),
            }

    if http_method == "POST" and path == "/invoices/vendors/add":
        """Add a new vendor"""
        try:
            body = json.loads(event.get("body", "{}"))
            if not body:
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({"message": "Invalid request body"}),
                }
            tables = get_tables()
            tables["vendors"].put_item(Item=body)
            return {
                "statusCode": 201,
                "headers": headers,
                "body": json.dumps(
                    {"message": "Vendor added successfully"}
                ),
            }

        except Exception as e:
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"message": str(e)}),
            }

    # Handle unrecognized requests
    return {
        "statusCode": 404,
        "headers": headers,
        "body": json.dumps({"message": "Not found"}),
    }
