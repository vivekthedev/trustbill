import base64
import json
import os
from io import BytesIO
import boto3
import pytest
from moto import mock_s3, mock_events
from unittest.mock import patch, MagicMock

# Import the function to test
from trustbill.extract.extract import lambda_handler


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def s3_bucket(aws_credentials):
    """Create mock S3 bucket."""
    with mock_s3():
        s3 = boto3.client('s3')
        bucket_name = "serverless-trustbill-invoices"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name


@pytest.fixture
def eventbridge(aws_credentials):
    """Create mock EventBridge."""
    with mock_events():
        eventbridge = boto3.client('events')
        yield eventbridge


@patch('boto3.client')
def test_lambda_handler_success(mock_boto3_client, s3_bucket, eventbridge):
    """Test successful lambda_handler execution."""
    # Mock Bedrock client response
    mock_bedrock = MagicMock()
    mock_bedrock.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": """```json
                        {
                            "InvoiceNumber": "INV-123",
                            "InvoiceDate": "2023-06-01",
                            "DueDate": "2023-07-01",
                            "Currency": "USD",
                            "TotalAmount": "1000",
                            "TaxAmount": "100",
                            "VendorName": "Test Vendor",
                            "VendorAddress": "123 Test St",
                            "VendorGSTIN": "TEST123456",
                            "VendorBankName": "Test Bank",
                            "VendorBankAccount": "12345678",
                            "VendorIFSCCode": "TESTCODE",
                            "VendorBankRoutingNumber": "987654",
                            "CustomerName": "Test Customer",
                            "CustomerAddress": "456 Test Ave",
                            "CustomerGSTIN": "CUST123456",
                            "LineItems": [],
                            "PaymentTerms": "30 days",
                            "PaymentMethod": "Bank Transfer",
                            "Notes": "Test note",
                            "TermsAndConditions": "Test terms"
                        }```"""
                    }
                ]
            }
        }
    }
    
    # Mock S3 and EventBridge clients
    mock_s3 = MagicMock()
    mock_eventbridge = MagicMock()
    mock_eventbridge.put_events.return_value = {"FailedEntryCount": 0}
    
    # Configure mock_boto3_client to return our mock clients
    def side_effect(service, *args, **kwargs):
        if service == 'bedrock-runtime':
            return mock_bedrock
        elif service == 's3':
            return mock_s3
        elif service == 'events':
            return mock_eventbridge
        return MagicMock()

    mock_boto3_client.side_effect = side_effect
    
    # Mock API Gateway event with base64 encoded PDF content
    pdf_content = b"Test PDF content"
    base64_pdf = base64.b64encode(pdf_content).decode()
    
    event = {
        "body": json.dumps({
            "TextBody": "From: Test User <test@example.com>\nSubject: Invoice",
            "Attachments": [
                {
                    "Content": base64_pdf,
                    "ContentType": "application/pdf",
                    "Name": "invoice.pdf"
                }
            ]
        })
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify response
    assert response["statusCode"] == 200
    assert response["body"] == "file processed"
    
    # Verify Bedrock was called
    mock_bedrock.converse.assert_called_once()
    
    # Verify S3 upload was attempted
    mock_s3.upload_fileobj.assert_called_once()
    
    # Verify EventBridge event was sent
    mock_eventbridge.put_events.assert_called_once()


@patch('boto3.client')
def test_lambda_handler_invalid_request(mock_boto3_client):
    """Test lambda_handler with invalid request."""
    # Empty event
    event = {}
    response = lambda_handler(event, {})
    assert response["statusCode"] == 400
    
    # Missing Attachments
    event = {
        "body": json.dumps({
            "TextBody": "Test"
        })
    }
    response = lambda_handler(event, {})
    assert response["statusCode"] == 400


@patch('boto3.client')
def test_lambda_handler_bedrock_error(mock_boto3_client, s3_bucket):
    """Test lambda_handler when Bedrock API call fails."""
    # Mock Bedrock client that raises an exception
    mock_bedrock = MagicMock()
    mock_bedrock.converse.side_effect = Exception("Bedrock API error")
    
    # Create mock clients for other services
    mock_s3 = MagicMock()
    mock_eventbridge = MagicMock()
    
    # Configure mock_boto3_client to return our mock clients
    def side_effect(service, *args, **kwargs):
        if service == 'bedrock-runtime':
            return mock_bedrock
        elif service == 's3':
            return mock_s3
        elif service == 'events':
            return mock_eventbridge
        return MagicMock()  # Return a generic mock for other services

    mock_boto3_client.side_effect = side_effect
    
    # Create test event
    pdf_content = b"Test PDF content"
    base64_pdf = base64.b64encode(pdf_content).decode()
    
    event = {
        "body": json.dumps({
            "TextBody": "From: Test User <test@example.com>\nSubject: Invoice",
            "Attachments": [
                {
                    "Content": base64_pdf,
                    "ContentType": "application/pdf",
                    "Name": "invoice.pdf"
                }
            ]
        })
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify error response
    assert response["statusCode"] == 500
    assert "Error processing file" in json.loads(response["body"])["message"]
