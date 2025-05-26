#!/usr/bin/env python3
import os
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_fastapi():
    """Run the FastAPI application"""
    import uvicorn
    port = int(os.getenv("APP_PORT", 8000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=debug)

def run_streamlit():
    """Run the Streamlit application"""
    import subprocess
    subprocess.run(["streamlit", "run", "app/streamlit_app.py"])

def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description="Mind Map Generator")
    parser.add_argument("--app", type=str, choices=["fastapi", "streamlit"], default="fastapi",
                        help="Application to run (fastapi or streamlit)")
    args = parser.parse_args()
    
    if args.app == "streamlit":
        run_streamlit()
    else:
        run_fastapi()

if __name__ == "__main__":
    main()