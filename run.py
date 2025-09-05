# run.py

import os
import logging
from app import create_app
from dotenv import load_dotenv

# Set up logging to help diagnose issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

try:
    logger.info("Starting app creation...")
    app = create_app()
    logger.info("App created successfully")
except Exception as e:
    logger.error(f"Failed to create app: {str(e)}")
    logger.error(f"Error type: {type(e).__name__}")
    raise

if __name__ == '__main__':
    logger.info("Starting Flask development server...")
    app.run(debug=True, host='0.0.0.0')

