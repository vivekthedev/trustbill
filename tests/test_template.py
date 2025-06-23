import subprocess
import json
import os
import pytest


def test_template_file_exists():
    """Test that the template file exists."""
    assert os.path.isfile("template.yaml"), "template.yaml file not found"


def test_sam_template_valid():
    """Test that the SAM template is valid."""
    try:
        result = subprocess.run(
            ["sam", "validate", "--template", "template.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"SAM template validation failed: {result.stderr}"
    except FileNotFoundError:
        pytest.skip("AWS SAM CLI not found in PATH. Install it with 'pip install aws-sam-cli'.")

