#!/usr/bin/env python3
"""
Startup script for Praxis AI backend
Handles initialization and health checks
"""

import os
import sys
import time
import traceback
from dotenv import load_dotenv

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"WARNING: Missing environment variables: {missing_vars}")
        return False
    
    print("Environment variables check passed.")
    return True

def check_dependencies():
    """Check if required Python packages are available"""
    try:
        import fastapi
        import uvicorn
        import psycopg2
        import sentence_transformers
        print("All required packages are available.")
        return True
    except ImportError as e:
        print(f"ERROR: Missing required package: {e}")
        return False

def main():
    """Main startup function"""
    print("=== Praxis AI Backend Startup ===")
    
    # Load environment variables
    script_dir = os.path.dirname(__file__)
    dotenv_path = os.path.join(script_dir, '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(".env file loaded.")
    else:
        print("WARNING: .env file not found.")
    
    # Check environment
    if not check_environment():
        print("WARNING: Environment check failed. Some features may not work.")
    
    # Check dependencies
    if not check_dependencies():
        print("ERROR: Dependency check failed. Exiting.")
        sys.exit(1)
    
    print("Startup checks completed successfully.")
    print("Starting FastAPI application...")

if __name__ == "__main__":
    main()
