import base64
import json
import os
import re
import uuid
from datetime import datetime
from io import BytesIO

import boto3

BUCKET_NAME = "serverless-trustbill-invoices"
system_prompt = """
    You are an AI invoice parser. Extract the following fields from this document image and return the result in a valid JSON object. If a field is not present, return it as null.

    Required fields:
    - InvoiceNumber
    - InvoiceDate
    - DueDate
    - Currency
    - TotalAmount
    - TaxAmount
    - VendorName
    - VendorAddress
    - VendorGSTIN
    - VendorBankName
    - VendorBankAccount
    - VendorIFSCCode
    - VendorBankRoutingNumber
    - CustomerName
    - CustomerAddress
    - CustomerGSTIN
    - LineItems (list of objects with Description, Quantity, UnitPrice, Amount)
    - PaymentTerms
    - PaymentMethod
    - Notes
    - TermsAndConditions


    Output strictly as valid JSON.
    {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "InvoiceData",
    "type": "object",
    "properties": {
        "InvoiceNumber": { "type": ["string", "null"] },
        "InvoiceDate": { "type": ["string", "null"], "format": "date" },
        "DueDate": { "type": ["string", "null"], "format": "date" },
        "Currency": { "type": ["string", "null"] },
        "TotalAmount": { "type": ["number", "null"] },
        "TaxAmount": { "type": ["number", "null"] },
        "VendorName": { "type": ["string", "null"] },
        "VendorAddress": { "type": ["string", "null"] },
        "VendorGSTIN": { "type": ["string", "null"] },
        "VendorBankName": { "type": ["string", "null"] },
        "VendorBankAccount": { "type": ["string", "null"] },
        "VendorIFSCCode": { "type": ["string", "null"] },
        "VendorBankRoutingNumber": { "type": ["string", "null"] },
        "CustomerName": { "type": ["string", "null"] },
        "CustomerAddress": { "type": ["string", "null"] },
        "CustomerGSTIN": { "type": ["string", "null"] },
        "LineItems": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
            "Description": { "type": ["string", "null"] },
            "Quantity": { "type": ["number", "null"] },
            "UnitPrice": { "type": ["number", "null"] },
            "Amount": { "type": ["number", "null"] }
            },
            "required": ["Description", "Quantity", "UnitPrice", "Amount"]
        }
        },
        "PaymentTerms": { "type": ["string", "null"] },
        "PaymentMethod": { "type": ["string", "null"] },
        "Notes": { "type": ["string", "null"] },
        "TermsAndConditions": { "type": ["string", "null"] }
    },
    "required": [
        "InvoiceNumber",
        "InvoiceDate",
        "DueDate",
        "TaxAmount",
        "Currency",
        "TotalAmount",
        "VendorName",
        "VendorAddress",
        "VendorGSTIN",
        "VendorBankName",
        "VendorBankAccount",
        "VendorIFSCCode",
        "VendorBankRoutingNumber",
        "CustomerName",
        "CustomerAddress",
        "CustomerGSTIN",
        "LineItems",
        "PaymentTerms",
        "PaymentMethod",
        "Notes",
        "TermsAndConditions"      
    ]
    }
"""
MODEL_ID = "us.amazon.nova-premier-v1:0"
prompt = """
    ## Task
    Process the provided invoice. 

    ## Invoice 
    {invoice} 

    Provide your response immediately without any preamble or additional information
"""


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}") or "{}")
    if not body:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Invalid request body"}),
        }
    if "TextBody" not in body or "Attachments" not in body:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Missing required fields in request body"}),
        }

    s3 = boto3.client("s3")
    eventbridge = boto3.client("events")

    regexbody = re.search(r"From:.*?<([^<>]+@[^<>]+)>", body["TextBody"])
    if regexbody:
        sender_email = regexbody.group(1)
    else:
        sender_email = body["From"]

    email_text = body["TextBody"]
    document_bytes = base64.b64decode(body["Attachments"][0]["Content"])
    file_key = f"invoice-{uuid.uuid4()}.pdf"
    bedrock_client = boto3.client("bedrock-runtime", "us-east-1")
    try:
        response = bedrock_client.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "document": {
                                "format": "pdf",
                                "name": "invoice",
                                "source": {
                                    "bytes": document_bytes,
                                },
                            },
                        },
                        {"text": prompt},
                    ],
                },
            ],
            system=[{"text": system_prompt}],
        )
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error processing file with error: {e}"}),
        }
    output = response["output"]["message"]["content"][0]["text"]
    cleaned_output = output.strip("```").strip("json").strip()
    try:
        s3.upload_fileobj(
            BytesIO(document_bytes),
            BUCKET_NAME,
            file_key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "ACL": "public-read",
                "Metadata": {
                    "sender_email": sender_email,
                    "timestamp": datetime.now().isoformat(),
                },
            },
        )
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": f"Error uploading file to S3 with error: {e}"}
            ),
        }
    file_url = f"https://{BUCKET_NAME}.s3.us-east-1.amazonaws.com/{file_key}"

    try:
        json_output = json.loads(cleaned_output)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        json_output = {}

    json_output["VendorEmail"] = sender_email
    json_output["FileURL"] = file_url
    json_output["InvoiceId"] = str(uuid.uuid4())
    json_output["TextBody"] = email_text
    try:
        eventbridge_response = eventbridge.put_events(
            Entries=[
                {
                    "Source": "trustbill.extract",
                    "DetailType": "InvoiceExtracted",
                    "Detail": json.dumps(json_output),
                    "Time": datetime.now(),
                }
            ]
        )
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Failed to send event to EventBridge", "error": str(e)}
            ),
        }

    return {"statusCode": 200, "body": "file processed"}
