import os
import logging
from flask import Flask, request, jsonify, g, render_template, redirect, url_for, session
from config import Config
from database import db, init_db_for_tenant, get_tenant_db_session, close_db_session
from dotenv import load_dotenv
# Import models from the centralized models.py to avoid conflicts
from app.models import User

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# NOTE: This create_app function is deprecated in favor of app/__init__.py
# Keeping it for backward compatibility but redirecting to the main factory
def create_app():
    logger.info("Using deprecated app.py create_app - redirecting to app/__init__.py")
    from app import create_app as main_create_app
    return main_create_app()