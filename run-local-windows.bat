@echo off
REM Quick script to run API server locally on Windows with visible browser
echo ========================================
echo Starting API Server (Localhost - Windows)
echo Browser windows will be VISIBLE
echo ========================================
echo.

REM Set environment variable for visible browser
set HEADLESS_BROWSER=false

REM Check if .env file exists, if not create one
if not exist .env (
    echo Creating .env file with HEADLESS_BROWSER=false...
    echo HEADLESS_BROWSER=false > .env
)

REM Run the API server
echo Starting Flask API server...
echo Server will run on http://localhost:8080
echo Press Ctrl+C to stop
echo.
python api_server.py

pause

