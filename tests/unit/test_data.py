import json
import os
import pytest
import boto3
from moto import mock_dynamodb

# Set environment variables before importing the module
os.environ["TrustedVendorsTable"] = "test-vendors-table"
os.environ["InvoicesTable"] = "test-invoices-table"

# Import the functions to test
from trustbill.data.data import lambda_handler, get_all_data, unflag_invoice


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create mock DynamoDB tables for testing."""
    with mock_dynamodb():
        # Create DynamoDB resource
        dynamodb = boto3.resource("dynamodb")
        
        # Create vendors table
        vendors_table = dynamodb.create_table(
            TableName="test-vendors-table",
            KeySchema=[{"AttributeName": "vendorId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "vendorId", "AttributeType": "S"},
                {"AttributeName": "VendorEmail", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "VendorEmailIndex",
                    "KeySchema": [{"AttributeName": "VendorEmail", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
        )
        
        # Create invoices table
        invoices_table = dynamodb.create_table(
            TableName="test-invoices-table",
            KeySchema=[{"AttributeName": "invoiceId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "invoiceId", "AttributeType": "S"},
                {"AttributeName": "VendorEmail", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "VendorEmailIndex", 
                    "KeySchema": [{"AttributeName": "VendorEmail", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
        )
        
        # Add some test data
        vendors_table.put_item(
            Item={
                "vendorId": "vendor123",
                "VendorEmail": "test@example.com",
                "VendorName": "Test Vendor"
            }
        )
        
        invoice_flags = {
            "IncorrectVendorInfo": True,
            "DuplicateInvoice": False
        }
        
        invoices_table.put_item(
            Item={
                "invoiceId": "invoice123",
                "VendorEmail": "test@example.com",
                "InvoiceNumber": "INV-001",
                "TotalAmount": "1000",
                "Flags": invoice_flags
            }
        )
        
        yield {
            "vendors_table": vendors_table,
            "invoices_table": invoices_table
        }


def test_get_all_data(dynamodb_tables):
    """Test get_all_data function."""
    # Call the function
    result = get_all_data()
    
    # Check the result
    assert "vendors" in result
    assert "invoices" in result
    assert len(result["vendors"]) == 1
    assert len(result["invoices"]) == 1
    assert result["vendors"][0]["vendorId"] == "vendor123"
    assert result["invoices"][0]["invoiceId"] == "invoice123"


def test_unflag_invoice(dynamodb_tables):
    """Test unflag_invoice function."""
    # Test unflagging an existing invoice
    result = unflag_invoice("invoice123")
    
    # Verify the result
    assert result["success"] is True
    assert "invoice123" in result["message"]
    
    # Verify the invoice was updated in DynamoDB
    updated_invoice = dynamodb_tables["invoices_table"].get_item(
        Key={"invoiceId": "invoice123"}
    ).get("Item")
    
    # Check if flags were updated
    flags = updated_invoice.get("Flags", "{}")
    assert flags["IncorrectVendorInfo"] is False
    assert flags["DuplicateInvoice"] is False


def test_unflag_nonexistent_invoice(dynamodb_tables):
    """Test unflagging a non-existent invoice."""
    result = unflag_invoice("non-existent")
    
    # Should return failure
    assert result["success"] is False
    assert "not found" in result["message"]


def test_lambda_handler_get_invoices(dynamodb_tables):
    """Test GET /invoices endpoint."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "GET",
        "path": "/invoices",
        "resource": "/invoices"
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "vendors" in body
    assert "invoices" in body
    assert len(body["vendors"]) == 1
    assert len(body["invoices"]) == 1


def test_lambda_handler_put_invoices(dynamodb_tables):
    """Test PUT /invoices/{invoiceId} endpoint."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "PUT",
        "path": "/invoices/invoice123",
        "resource": "/invoices/{invoiceId}",
        "pathParameters": {
            "invoiceId": "invoice123"
        }
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True


def test_lambda_handler_missing_invoice_id(dynamodb_tables):
    """Test PUT /invoices/{invoiceId} with missing invoiceId."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "PUT",
        "path": "/invoices/",
        "resource": "/invoices/{invoiceId}",
        "pathParameters": {}
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "invoiceId is required" in body["message"]


def test_lambda_handler_add_vendor(dynamodb_tables):
    """Test POST /invoices/vendors/add endpoint."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "POST",
        "path": "/invoices/vendors/add",
        "body": json.dumps({
            "vendorId": "new-vendor-123",
            "VendorEmail": "new@example.com",
            "VendorName": "New Vendor"
        })
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 201
    
    # Verify the vendor was added to DynamoDB
    vendors = list(dynamodb_tables["vendors_table"].scan()["Items"])
    assert len(vendors) == 2
    new_vendor = next((v for v in vendors if v["vendorId"] == "new-vendor-123"), None)
    assert new_vendor is not None
    assert new_vendor["VendorEmail"] == "new@example.com"


def test_lambda_handler_options(dynamodb_tables):
    """Test OPTIONS request for CORS."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "OPTIONS",
        "path": "/invoices"
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


def test_lambda_handler_not_found(dynamodb_tables):
    """Test handling of unrecognized paths."""
    # Create a mock API Gateway event
    event = {
        "httpMethod": "GET",
        "path": "/unknown",
        "resource": "/unknown"
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Not found" in body["message"]
