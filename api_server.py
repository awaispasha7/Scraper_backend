"""
Simple Flask API server for Railway deployment
Provides endpoints to trigger scraper and check status
"""

from flask import Flask, jsonify, request
import subprocess
import os
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Global variables to track scraper status
scraper_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "error": None
}

def run_scraper():
    """Run the scraper in a separate thread"""
    global scraper_status
    
    if scraper_status["running"]:
        return {"error": "Scraper is already running"}
    
    scraper_status["running"] = True
    scraper_status["error"] = None
    scraper_status["last_run"] = datetime.now().isoformat()
    
    def execute_scraper():
        try:
            # Run the scraper script
            result = subprocess.run(
                ["python3", "forsalebyowner_selenium_scraper.py"],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            scraper_status["last_result"] = {
                "success": result.returncode == 0,
                "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
                "stderr": result.stderr[-1000:] if result.stderr else "",  # Last 1000 chars
                "returncode": result.returncode
            }
            
            if result.returncode != 0:
                scraper_status["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            scraper_status["error"] = "Scraper timed out after 1 hour"
            scraper_status["last_result"] = {"success": False, "error": "Timeout"}
        except Exception as e:
            scraper_status["error"] = str(e)
            scraper_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            scraper_status["running"] = False
    
    # Start scraper in background thread
    thread = threading.Thread(target=execute_scraper)
    thread.daemon = True
    thread.start()
    
    return {"message": "Scraper started", "started_at": scraper_status["last_run"]}

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "ForSaleByOwner Scraper API",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get scraper status"""
    return jsonify({
        "status": "running" if scraper_status["running"] else "idle",
        "last_run": scraper_status["last_run"],
        "last_result": scraper_status["last_result"],
        "error": scraper_status["error"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/trigger', methods=['POST'])
def trigger_scraper():
    """Trigger the scraper"""
    result = run_scraper()
    return jsonify(result)

@app.route('/api/trigger', methods=['GET'])
def trigger_scraper_get():
    """Trigger the scraper via GET (for easy testing)"""
    result = run_scraper()
    return jsonify(result)

if __name__ == '__main__':
    # Get port from environment variable or use default 8080
    port = int(os.environ.get('PORT', 8080))
    # Run on 0.0.0.0 to accept connections from outside
    app.run(host='0.0.0.0', port=port, debug=False)

