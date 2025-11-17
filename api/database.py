"""
Database connection utilities for Energy Forecast Agent
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Create and return a database connection.
    Returns a connection with RealDictCursor for dict-like results.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "energy_forecast"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def test_connection() -> bool:
    """
    Test if database connection is working.
    Returns True if connection successful, False otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
