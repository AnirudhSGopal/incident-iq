"""
IncidentIQ configuration module.
Loads environment variables and configuration settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from a local .env file before reading any os.environ values
load_dotenv()

REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-west-2"))
LOG_GROUP = os.environ.get("LOG_GROUP", "/incident-iq/demo")
LOG_STREAM = os.environ.get("LOG_STREAM", "incident-001")

