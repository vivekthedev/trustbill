import json
import os
import boto3
import pytest
from moto import mock_dynamodb
from boto3.dynamodb.conditions import Key

# Set environment variables before importing the module
os.environ["TrustedVendorsTable"] = "test-vendors-table"
os.environ["InvoicesTable"] = "test-invoices-table"

# Import the functions to test
from trustbill.verify.verify import (
    lambda_handler, 
    incorrect_vendor_info,
    changed_bank_details, 
    duplicate_invoice, 
    unusual_amounts
)


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
        
        # Add test data to vendors table
        vendors_table.put_item(
            Item={
                "vendorId": "vendor123",
                "VendorEmail": "test@example.com",
                "VendorName": "Test Vendor",
                "VendorBankName": "Test Bank",
                "VendorBankAccount": "12345678",
                "VendorIFSCCode": "TESTCODE",
                "VendorBankRoutingNumber": "987654"
            }
        )
        
        # Add test data to invoices table
        invoices_table.put_item(
            Item={
                "invoiceId": "invoice123",
                "VendorEmail": "test@example.com",
                "InvoiceNumber": "INV-001",
                "TotalAmount": "1000"
            }
        )
        
        yield {
            "vendors_table": vendors_table,
            "invoices_table": invoices_table
        }


def test_incorrect_vendor_info_new_vendor(dynamodb_tables):
    """Test incorrect_vendor_info for a new vendor."""
    invoice_data = {
        "VendorEmail": "new@example.com",
        "VendorBankName": "New Bank"
    }
    
    # Should return True for a new vendor
    assert incorrect_vendor_info(invoice_data) is True


def test_incorrect_vendor_info_changed_details(dynamodb_tables):
    """Test incorrect_vendor_info for a vendor with changed bank details."""
    invoice_data = {
        "VendorEmail": "test@example.com",
        "VendorBankName": "Different Bank",  # Changed from "Test Bank"
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }
    
    # Should return True because bank name changed
    assert incorrect_vendor_info(invoice_data) is True


def test_incorrect_vendor_info_same_details(dynamodb_tables):
    """Test incorrect_vendor_info for a vendor with same bank details."""
    invoice_data = {
        "VendorEmail": "test@example.com",
        "VendorBankName": "Test Bank",
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }
    
    # Should return False because details are the same
    assert incorrect_vendor_info(invoice_data) is False


def test_changed_bank_details_true(dynamodb_tables):
    """Test changed_bank_details when details have changed."""
    vendor_data = [{
        "VendorBankName": "Test Bank",
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }]
    
    invoice_data = {
        "VendorBankName": "Other Bank",  # Different
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }
    
    assert changed_bank_details(vendor_data, invoice_data) is True


def test_changed_bank_details_false(dynamodb_tables):
    """Test changed_bank_details when details are the same."""
    vendor_data = [{
        "VendorBankName": "Test Bank",
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }]
    
    invoice_data = {
        "VendorBankName": "Test Bank",
        "VendorBankAccount": "12345678",
        "VendorIFSCCode": "TESTCODE",
        "VendorBankRoutingNumber": "987654"
    }
    
    assert changed_bank_details(vendor_data, invoice_data) is False


def test_duplicate_invoice(dynamodb_tables):
    """Test duplicate_invoice detection."""
    # Add a duplicate invoice for testing
    invoice_data = {
        "VendorEmail": "test@example.com",
        "InvoiceNumber": "INV-001"  # Same as existing invoice
    }
    
    # Should return True for duplicate
    assert duplicate_invoice("test@example.com", invoice_data) is True
    
    # Should return False for new invoice number
    invoice_data["InvoiceNumber"] = "INV-002"
    assert duplicate_invoice("test@example.com", invoice_data) is False


def test_unusual_amounts(dynamodb_tables):
    """Test unusual_amounts detection."""
    # Add more invoices to establish a pattern
    for i in range(2, 5):
        dynamodb_tables["invoices_table"].put_item(
            Item={
                "invoiceId": f"invoice{i}",
                "VendorEmail": "test@example.com",
                "InvoiceNumber": f"INV-00{i}",
                "TotalAmount": "1000"  # Consistent amount
            }
        )
    
    # Test with a normal amount
    invoice_data = {
        "VendorEmail": "test@example.com",
        "TotalAmount": "1100"  # Only 10% higher
    }
    # Should not flag as unusual
    assert unusual_amounts(invoice_data) is False
    
    # Test with an unusually high amount
    invoice_data["TotalAmount"] = "2500"  # 150% higher
    # Should flag as unusual
    assert unusual_amounts(invoice_data) is True


def test_lambda_handler(dynamodb_tables):
    """Test lambda_handler function."""
    # Create a mock EventBridge event
    event = {
        "detail": {
            "VendorEmail": "new@example.com",
            "VendorName": "New Vendor",
            "VendorAddress": "123 Test St",
            "VendorGSTIN": "TEST123456",
            "VendorBankName": "New Bank",
            "VendorBankAccount": "87654321",
            "VendorIFSCCode": "NEWCODE",
            "VendorBankRoutingNumber": "123456",
            "InvoiceNumber": "INV-100",
            "InvoiceDate": "2023-06-01",
            "DueDate": "2023-07-01",
            "Currency": "USD",
            "TotalAmount": "2000",
            "TaxAmount": "200",
            "LineItems": [],
            "FileURL": "https://example.com/invoice.pdf"
        }
    }
    
    # Call the Lambda handler
    response = lambda_handler(event, {})
    
    # Verify the response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "flags" in body
    
    # Verify the invoice was saved to DynamoDB
    invoices = list(dynamodb_tables["invoices_table"].scan()["Items"])
    new_invoices = [i for i in invoices if i["VendorEmail"] == "new@example.com"]
    assert len(new_invoices) > 0
    new_invoice = new_invoices[0]
    assert new_invoice["InvoiceNumber"] == "INV-100"
    assert new_invoice["TotalAmount"] == "2000"
    
    # Check that flags were correctly set
    assert "Flags" in new_invoice
    flags = new_invoice["Flags"]
    assert flags["IncorrectVendorInfo"] is True
    assert flags["ItemizedInvoice"] is True
