import json
import os
import uuid

import boto3
from boto3.dynamodb.conditions import Attr, Key

VENDORS_TABLE = os.getenv("TrustedVendorsTable", None)
INVOICES_TABLE = os.getenv("InvoicesTable", None)
dynamodb = boto3.resource("dynamodb")

def get_tables():
    """Get DynamoDB tables. Lazy loading to support testing."""
    return {
        "vendors": dynamodb.Table(VENDORS_TABLE),
        "invoices": dynamodb.Table(INVOICES_TABLE)
    }


def incorrect_vendor_info(current_invoice_data):
    tables = get_tables()
    response = tables["vendors"].query(
        IndexName="VendorEmailIndex",
        KeyConditionExpression=Key("VendorEmail").eq(
            current_invoice_data.get("VendorEmail")
        ),
    )
    vendor_data = response.get("Items", [])
    if not vendor_data:
        return True

    return changed_bank_details(vendor_data, current_invoice_data)


def changed_bank_details(vendor_data, current_invoice_data):
    for item in vendor_data:
        if (
            (item.get("VendorBankName") != current_invoice_data.get("VendorBankName"))
            or (
                item.get("VendorBankAccount")
                != current_invoice_data.get("VendorBankAccount")
            )
            or (
                item.get("VendorIFSCCode") != current_invoice_data.get("VendorIFSCCode")
            )
            or (
                item.get("VendorBankRoutingNumber")
                != current_invoice_data.get("VendorBankRoutingNumber")
            )
        ):
            return True
    return False


def duplicate_invoice(vendor_email, current_invoice_data):

    tables = get_tables()
    response = tables["invoices"].query(
        IndexName="VendorEmailIndex",
        KeyConditionExpression=Key("VendorEmail").eq(vendor_email),
        FilterExpression=Attr("InvoiceNumber").eq(current_invoice_data.get("InvoiceNumber"))
    )
    # If we find any items with the same vendor email and invoice number, it's a duplicate
    if response.get("Items") and len(response.get("Items")) > 0:
        return True
    return False


def unusual_amounts(current_invoice_data):
    tables = get_tables()
    response = tables["invoices"].query(
        IndexName="VendorEmailIndex",
        KeyConditionExpression=Key("VendorEmail").eq(
            current_invoice_data.get("VendorEmail")
        ),
    )
    items = response.get("Items", [])
    if items:
        amounts = [
            float(item.get("TotalAmount", 0))
            for item in items
            if item.get("TotalAmount")
        ]
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            current_amount = float(current_invoice_data.get("TotalAmount", 0))
            if avg_amount > 0:
                deviation = abs(current_amount - avg_amount) / avg_amount * 100
                if deviation > 30:
                    return True
            return False
    else:
        return False

def lambda_handler(event, context):
    data = event.get("detail")
    vendorInfo = {
        "vendorId": str(uuid.uuid4()),
        "VendorEmail": data.get("VendorEmail"),
        "VendorName": data.get("VendorName"),
        "VendorAddress": data.get("VendorAddress"),
        "VendorGSTIN": data.get("VendorGSTIN"),
        "VendorBankName": data.get("VendorBankName"),
        "VendorBankAccount": data.get("VendorBankAccount"),
        "VendorIFSCCode": data.get("VendorIFSCCode"),
        "VendorBankRoutingNumber": data.get("VendorBankRoutingNumber"),
    }
    flags = {
        "IncorrectVendorInfo": False,
        "DuplicateInvoice": None,
        "UnusualAmounts": None,
        "ItemizedInvoice": False,
    }

    flags["IncorrectVendorInfo"] = incorrect_vendor_info(data)
    if not flags["IncorrectVendorInfo"]:
        flags["DuplicateInvoice"] = duplicate_invoice(data.get("VendorEmail"), data)
        flags["UnusualAmounts"] = unusual_amounts(data)
    if len(data.get("LineItems", [])) == 0:
        flags["ItemizedInvoice"] = True

    tables = get_tables()
    data["TotalAmount"] = str(data.get("TotalAmount", "-"))
    data["TaxAmount"] = str(data.get("TaxAmount", "-"))
    
    for item in data.get("LineItems", []):
        for k, v in item.items():
            if isinstance(v, (int, float)):
                item[k] = str(v)
            elif v is None:
                item[k] = "-"

    tables["invoices"].put_item(
        Item={
            "invoiceId": str(uuid.uuid4()),
            "VendorEmail":data.get("VendorEmail"),
            "InvoiceNumber":data.get("InvoiceNumber"),
            "InvoiceDate":data.get("InvoiceDate"),
            "DueDate":data.get("DueDate"),
            "Currency":data.get("Currency"),
            "TotalAmount":data.get("TotalAmount"),
            "TaxAmount":data.get("TaxAmount"),
            "Items": data.get("LineItems", []),
            "Notes": data.get("Notes"),
            "TermsAndConditions": data.get("TermsAndConditions"),
            "FileURL": data.get("FileURL"),
            "Flags": flags,
            "VendorInfo": vendorInfo,
        }
    )
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Invoice verification completed", "flags": flags}
        ),
    }
