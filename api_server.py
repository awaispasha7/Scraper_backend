"""
Simple Flask API server for Railway deployment
Provides endpoints to trigger scraper and check status
"""


from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import os
import threading
import sys
import time
import queue
import schedule
from datetime import datetime

# Import URL detection and routing utilities
from utils.url_detector import URLDetector
from utils.table_router import TableRouter

app = Flask(__name__)
# Enable CORS for all routes - allows frontend to call backend API
# Explicitly allow all origins and methods for Railway deployment
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global status dictionaries
scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
apartments_scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_fsbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_frbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
hotpads_status = {"running": False, "last_run": None, "last_result": None, "error": None}
redfin_status = {"running": False, "last_run": None, "last_result": None, "error": None}
trulia_status = {"running": False, "last_run": None, "last_result": None, "error": None}
all_scrapers_status = {"running": False, "last_run": None, "finished_at": None, "last_result": None, "error": None, "current_scraper": None, "completed": []}
enrichment_status = {"running": False, "last_run": None, "last_result": None, "error": None}

# Global process tracker for stopping
active_processes = {}
user_stopped_processes = set()  # Track processes stopped by user (to avoid logging as errors)
stop_all_requested = False

# Global Log Buffer
# List of dicts: { "timestamp": iso_str, "message": str, "type": "info"|"error"|"success" }
LOG_BUFFER = []
MAX_LOG_SIZE = 1000

def add_log(message, type="info"):
    """Add a log entry to the buffer"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "type": type
    }
    LOG_BUFFER.append(entry)
    # Print to server console as well, handled gracefully for Windows encoding
    try:
        print(f"[{entry['timestamp']}] [{type.upper()}] {message}")
    except UnicodeEncodeError:
        # Fallback for consoles that don't support special characters/emojis
        clean_message = message.encode('ascii', 'ignore').decode('ascii')
        print(f"[{entry['timestamp']}] [{type.upper()}] {clean_message}")
    
    # Keep buffer size manageable
    if len(LOG_BUFFER) > MAX_LOG_SIZE:
        LOG_BUFFER.pop(0)

def stream_output(process, scraper_name):
    """Read output from process and add to logs"""
    for line in iter(process.stdout.readline, ''):
        if line:
            add_log(f"[{scraper_name}] {line.strip()}", "info")
    process.stdout.close()

def run_process_with_logging(cmd, cwd, scraper_name, status_dict, env=None):
    """Run a subprocess and stream its output to logs"""
    try:
        add_log(f"Starting {scraper_name}...", "info")
        status_dict["running"] = True
        status_dict["error"] = None
        status_dict["last_run"] = datetime.now().isoformat()
        
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr into stdout for simple logging
            text=True,
            bufsize=1, # Line buffered
            universal_newlines=True,
            env=env
        )
        
        # Register process for stopping
        active_processes[scraper_name] = process
        
        # Read output in real-time
        stream_output(process, scraper_name)
        
        # Wait for completion
        returncode = process.wait()
        
        # Unregister
        if scraper_name in active_processes:
            del active_processes[scraper_name]
            
        success = returncode == 0
        status_dict["running"] = False
        
        # Check if this was a user-initiated stop (negative return codes indicate termination signals)
        was_user_stopped = scraper_name in user_stopped_processes or returncode < 0
        
        if success:
            result_info = {
                "success": True,
                "returncode": returncode,
                "timestamp": datetime.now().isoformat()
            }
            add_log(f"{scraper_name} completed successfully.", "success")
        elif was_user_stopped:
            # User-initiated stop (negative return code = termination signal like SIGTERM -15, SIGKILL -9)
            msg = f"{scraper_name} stopped by user."
            result_info = {
                "success": True,  # Treat as successful operation (user action, not error)
                "returncode": returncode,
                "stopped_by_user": True,
                "timestamp": datetime.now().isoformat()
            }
            add_log(msg, "info")
            # Remove from tracking set
            user_stopped_processes.discard(scraper_name)
        else:
            # Actual error - non-zero return code that wasn't user-initiated
            msg = f"{scraper_name} failed with return code {returncode}."
            result_info = {
                "success": False,
                "returncode": returncode,
                "error": msg,
                "timestamp": datetime.now().isoformat()
            }
            add_log(msg, "error")
            status_dict["error"] = msg
        
        status_dict["last_result"] = result_info
            
        return success
        
    except Exception as e:
        status_dict["running"] = False
        ensure_process_killed(scraper_name)
        err_msg = f"Error running {scraper_name}: {str(e)}"
        add_log(err_msg, "error")
        status_dict["error"] = err_msg
        status_dict["last_result"] = {"success": False, "error": str(e)}
        return False

def ensure_process_killed(scraper_name):
    """Kill process if it exists in active_processes"""
    process = active_processes.get(scraper_name)
    if process:
        # Mark as user-stopped so we don't log the termination as an error
        user_stopped_processes.add(scraper_name)
        try:
            process.terminate()
            time.sleep(1)
            if process.poll() is None:
                process.kill()
        except Exception as e:
            add_log(f"Error terminating {scraper_name}: {str(e)}", "error")
        
        # Safely remove from tracker
        active_processes.pop(scraper_name, None)

def run_sequential_scrapers():
    """Run all scrapers sequentially"""
    global stop_all_requested, all_scrapers_status
    
    if all_scrapers_status["running"]:
        add_log("⚠️ Sequential run triggered but already running. Skipping.", "warning")
        return

    stop_all_requested = False
    all_scrapers_status["running"] = True
    all_scrapers_status["error"] = None
    all_scrapers_status["last_run"] = datetime.now().isoformat()
    add_log("🚀 Starting ALL scrapers sequentially...", "info")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    scrapers = [
        ("FSBO", [sys.executable, "forsalebyowner_selenium_scraper.py"], os.path.join(base_dir, "FSBO_Scraper"), scraper_status),
        ("Apartments", [sys.executable, "-m", "scrapy", "crawl", "apartments_frbo"], os.path.join(base_dir, "Apartments_Scraper"), apartments_scraper_status),
        ("Zillow_FSBO", [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"], os.path.join(base_dir, "Zillow_FSBO_Scraper"), zillow_fsbo_status),
        ("Zillow_FRBO", [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"], os.path.join(base_dir, "Zillow_FRBO_Scraper"), zillow_frbo_status),
        ("Hotpads", [sys.executable, "-m", "scrapy", "crawl", "hotpads_scraper"], os.path.join(base_dir, "Hotpads_Scraper"), hotpads_status),
        ("Redfin", [sys.executable, "-m", "scrapy", "crawl", "redfin_spider"], os.path.join(base_dir, "Redfin_Scraper"), redfin_status),
        ("Trulia", [sys.executable, "-m", "scrapy", "crawl", "trulia_spider"], os.path.join(base_dir, "Trulia_Scraper"), trulia_status),
    ]
    
    for name, cmd, cwd, status_dict in scrapers:
        if stop_all_requested:
            add_log("🛑 Stop All requested. Cancelling remaining scrapers.", "warning")
            break
            
        all_scrapers_status["current_scraper"] = name
        add_log(f"--- Queue: Starting {name} ---", "info")
        
        # Run the scraper
        try:
            success = run_process_with_logging(cmd, cwd, name, status_dict)
            
            if not success:
                add_log(f"⚠️ {name} failed, but continuing with next scraper...", "error")
            else:
                add_log(f"✅ {name} finished successfully.", "success")
        except Exception as e:
             add_log(f"❌ Critical error executing {name}: {e}. Continuing...", "error")
        
        if stop_all_requested:
            add_log("🛑 Stop All requested. Cancelling remaining scrapers.", "warning")
            break
            
        time.sleep(2) # Brief pause between scrapers
        
    all_scrapers_status["running"] = False
    all_scrapers_status["current_scraper"] = None
    all_scrapers_status["finished_at"] = datetime.now().isoformat()
    if stop_all_requested:
            add_log("⏹️ Sequential run stopped by user.", "warning")
    else:
            add_log("🎉 ALL scrapers finished execution.", "success")

def scheduler_loop():
    """Background loop to check schedule"""
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_scheduler():
    """Start the scheduler thread"""
    # Schedule job every 24 hours (midnight)
    # You can change this to specific time: schedule.every().day.at("00:00").do(run_sequential_job_thread)
    # For now, let's stick to simple "every 24 hours" from start, or explicit time.
    # User asked for "after 24 hours". Let's use 24 hours interval or daily at midnight.
    # Daily at midnight is more robust.
    
    schedule.every().day.at("00:00").do(lambda: threading.Thread(target=run_sequential_scrapers, daemon=True).start())
    
    add_log("⏰ Scheduler started: Will run all scrapers daily at 00:00", "info")
    
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

# ==================================
# API ROUTES
# ==================================

@app.route('/', methods=['GET', 'OPTIONS'])
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check endpoint"""
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        return response
    
    response = jsonify({
        "status": "healthy",
        "service": "ForSaleByOwner Scraper API",
        "timestamp": datetime.now().isoformat()
    })
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/api/trigger', methods=['POST', 'GET'])
def trigger_scraper():
    """Trigger FSBO scraper"""
    if scraper_status["running"]:
        return jsonify({"error": "FSBO Scraper is already running"}), 400
    
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "FSBO_Scraper")
        run_process_with_logging(
            [sys.executable, "forsalebyowner_selenium_scraper.py"],
            scraper_dir,
            "FSBO",
            scraper_status
        )
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "FSBO scraper started"})

@app.route('/api/trigger-apartments', methods=['POST', 'GET'])
def trigger_apartments():
    if apartments_scraper_status["running"]:
        return jsonify({"error": "Apartments Scraper is already running"}), 400
    
    city = request.args.get("city", "chicago-il")
    
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Apartments_Scraper")
        run_process_with_logging(
             [sys.executable, "-m", "scrapy", "crawl", "apartments_frbo", "-a", f"city={city}"],
             scraper_dir,
             "Apartments",
             apartments_scraper_status
        )

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Apartments scraper started"})

@app.route('/api/status-apartments', methods=['GET'])
def get_apartments_status():
    return jsonify({
        "status": "running" if apartments_scraper_status["running"] else "idle",
        "last_run": apartments_scraper_status["last_run"],
        "error": apartments_scraper_status["error"]
    })

@app.route('/api/trigger-zillow-fsbo', methods=['POST', 'GET'])
def trigger_zillow_fsbo():
    if zillow_fsbo_status["running"]:
         return jsonify({"error": "Zillow FSBO Scraper is already running"}), 400
         
    url = request.args.get("url")
    cmd = [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"]
    if url:
        cmd.extend(["-a", f"start_url={url}"])
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Zillow_FSBO_Scraper")
        run_process_with_logging(cmd, scraper_dir, "Zillow_FSBO", zillow_fsbo_status)
        
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Zillow FSBO scraper started"})

@app.route('/api/status-zillow-fsbo', methods=['GET'])
def get_zillow_fsbo_status():
    return jsonify({
        "status": "running" if zillow_fsbo_status["running"] else "idle",
        "last_run": zillow_fsbo_status["last_run"],
        "error": zillow_fsbo_status["error"]
    })

@app.route('/api/trigger-zillow-frbo', methods=['POST', 'GET'])
def trigger_zillow_frbo():
    if zillow_frbo_status["running"]:
         return jsonify({"error": "Zillow FRBO Scraper is already running"}), 400
         
    url = request.args.get("url")
    cmd = [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"]
    if url:
        cmd.extend(["-a", f"start_url={url}"])
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Zillow_FRBO_Scraper")
        run_process_with_logging(cmd, scraper_dir, "Zillow_FRBO", zillow_frbo_status)
        
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Zillow FRBO scraper started"})

@app.route('/api/status-zillow-frbo', methods=['GET'])
def get_zillow_frbo_status():
    return jsonify({
        "status": "running" if zillow_frbo_status["running"] else "idle",
        "last_run": zillow_frbo_status["last_run"],
        "error": zillow_frbo_status["error"]
    })

@app.route('/api/trigger-hotpads', methods=['POST', 'GET'])
def trigger_hotpads():
    if hotpads_status["running"]:
        return jsonify({"error": "Hotpads Scraper is already running"}), 400
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Hotpads_Scraper")
        add_log("Manual trigger for Hotpads received from API", "info")
        run_process_with_logging(
            [sys.executable, "-m", "scrapy", "crawl", "hotpads_scraper"], 
            scraper_dir, 
            "Hotpads", 
            hotpads_status
        )
        
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Hotpads scraper started"})

@app.route('/api/status-hotpads', methods=['GET'])
def get_hotpads_status():
    return jsonify({
        "status": "running" if hotpads_status["running"] else "idle",
        "last_run": hotpads_status["last_run"],
        "error": hotpads_status["error"]
    })

@app.route('/api/trigger-redfin', methods=['POST', 'GET'])
def trigger_redfin():
    if redfin_status["running"]:
        return jsonify({"error": "Redfin Scraper is already running"}), 400
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Redfin_Scraper")
        run_process_with_logging(
            [sys.executable, "-m", "scrapy", "crawl", "redfin_spider"], 
            scraper_dir, 
            "Redfin", 
            redfin_status
        )
        
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Redfin scraper started"})

@app.route('/api/status-redfin', methods=['GET'])
def get_redfin_status():
    return jsonify({
        "status": "running" if redfin_status["running"] else "idle",
        "last_run": redfin_status["last_run"],
        "error": redfin_status["error"]
    })

@app.route('/api/trigger-trulia', methods=['POST', 'GET'])
def trigger_trulia():
    if trulia_status["running"]:
        return jsonify({"error": "Trulia Scraper is already running"}), 400
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_dir = os.path.join(base_dir, "Trulia_Scraper")
        run_process_with_logging(
            [sys.executable, "-m", "scrapy", "crawl", "trulia_spider"], 
            scraper_dir, 
            "Trulia", 
            trulia_status
        )
        
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Trulia scraper started"})

@app.route('/api/status-trulia', methods=['GET'])
def get_trulia_status():
    return jsonify({
        "status": "running" if trulia_status["running"] else "idle",
        "last_run": trulia_status["last_run"],
        "error": trulia_status["error"]
    })

@app.route('/api/test-search', methods=['GET'])
def test_search():
    """Test endpoint to verify server is responding"""
    print("=" * 80)
    print(f"[TEST] Test endpoint hit at {datetime.now().isoformat()}")
    print("=" * 80)
    import sys
    sys.stdout.flush()
    return jsonify({"status": "ok", "message": "Test endpoint working", "timestamp": datetime.now().isoformat()})

@app.route('/api/search-location', methods=['POST', 'GET', 'OPTIONS'])
def search_location():
    """Search a platform for a location and return the actual listing URL."""
    # Immediate log to verify endpoint is hit
    print("=" * 80)
    print(f"[SEARCH-LOCATION] Endpoint hit at {datetime.now().isoformat()}")
    print(f"[SEARCH-LOCATION] Method: {request.method}")
    print(f"[SEARCH-LOCATION] Headers: {dict(request.headers)}")
    print("=" * 80)
    add_log(f"SEARCH-LOCATION endpoint hit: method={request.method}", "info")
    
    # Handle CORS preflight - MUST be first thing we do
    if request.method == 'OPTIONS':
        add_log("SEARCH-LOCATION: Handling OPTIONS preflight", "info")
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        return response
    
    # Wrap EVERYTHING in try-except to prevent any crash
    import traceback
    import sys
    sys.stdout.flush()  # Force flush to ensure logs appear
    
    try:
        try:
            from utils.location_searcher import LocationSearcher
        except Exception as import_error:
            error_msg = f"Failed to import LocationSearcher: {str(import_error)}"
            add_log(error_msg, "error")
            response = jsonify({
                "error": error_msg,
                "error_type": "import_error"
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
        
        # Get platform and location from request
        try:
            print(f"[SEARCH-LOCATION] Request JSON: {request.is_json}")
            print(f"[SEARCH-LOCATION] Request data: {request.json if request.is_json else 'Not JSON'}")
            print(f"[SEARCH-LOCATION] Request args: {dict(request.args)}")
            sys.stdout.flush()
            
            if request.is_json and request.json:
                platform = request.json.get('platform')
                location = request.json.get('location')
            else:
                platform = request.args.get('platform') or (request.form.get('platform') if request.form else None)
                location = request.args.get('location') or (request.form.get('location') if request.form else None)
            
            print(f"[SEARCH-LOCATION] Parsed: platform={platform}, location={location}")
            sys.stdout.flush()
        except Exception as e:
            add_log(f"Error parsing request: {e}", "error")
            response = jsonify({"error": "Invalid request format"})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        if not platform:
            response = jsonify({"error": "Platform parameter is required"})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        if not location:
            response = jsonify({"error": "Location parameter is required"})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        try:
            print(f"[SEARCH-LOCATION] Starting search for platform={platform}, location={location}")
            sys.stdout.flush()
            add_log(f"Starting location search: platform={platform}, location={location}", "info")
            
            # For platforms with heavy bot detection, inform user it may take longer
            if platform.lower() in ['trulia', 'redfin', 'apartments.com']:
                add_log("⚠️ This platform has aggressive bot detection. Bypassing CAPTCHAs and anti-bot measures... This may take 30-90 seconds", "info")
            
            # Run the location search with timeout protection
            # Use threading to enforce a maximum timeout (90 seconds to stay under Gunicorn's 120s timeout)
            url = None
            error_occurred = None
            
            def run_search():
                nonlocal url, error_occurred
                try:
                    url = LocationSearcher.search_platform(platform, location)
                except Exception as e:
                    error_occurred = e
            
            import threading
            search_thread = threading.Thread(target=run_search, daemon=True)
            search_thread.start()
            search_thread.join(timeout=90)  # 90 second timeout (under Gunicorn's 120s)
            
            if search_thread.is_alive():
                # Thread is still running - it timed out
                add_log(f"Location search timed out after 90 seconds for {platform}/{location}", "error")
                response = jsonify({
                    "error": "Location search timed out. The operation took too long. Please try again or use Browserless.io for better performance.",
                    "platform": platform,
                    "location": location,
                    "error_type": "timeout"
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 504
            
            if error_occurred:
                # Selenium error occurred
                error_msg = str(error_occurred)
                add_log(f"Selenium error during location search: {error_msg}", "error")
                add_log(f"Selenium traceback: {traceback.format_exc()}", "error")
                
                response = jsonify({
                    "error": f"Browser automation failed: {error_msg}. Please ensure Chrome/Chromium is available on the server or set BROWSERLESS_TOKEN.",
                    "platform": platform,
                    "location": location,
                    "error_type": "selenium_error"
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 500
            
            if not url:
                add_log(f"Could not find URL for {platform}/{location}", "warning")
                response = jsonify({
                    "error": f"Could not find listing URL for '{location}' on {platform}",
                    "platform": platform,
                    "location": location
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 404
            
            # Validate the URL using URLDetector
            from utils.url_detector import URLDetector
            detected_platform, extracted_location = URLDetector.detect_and_extract(url)
            
            add_log(f"Location search successful: {platform}/{location} -> {url}", "success")
            response = jsonify({
                "url": url,
                "platform": detected_platform or platform,
                "location": extracted_location,
                "success": True
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        except Exception as inner_error:
            # Catch errors in the inner try block
            error_trace = traceback.format_exc()
            add_log(f"Error in location search: {inner_error}", "error")
            add_log(f"Traceback: {error_trace}", "error")
            response = jsonify({
                "error": f"Error searching location: {str(inner_error)}",
                "platform": platform if 'platform' in locals() else None,
                "location": location if 'location' in locals() else None
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
        
    except Exception as outer_error:
        # Catch ANY exception that wasn't caught above
        try:
            error_trace = traceback.format_exc()
            add_log(f"Unhandled error in search_location: {outer_error}", "error")
            add_log(f"Traceback: {error_trace}", "error")
            
            platform_val = platform if 'platform' in locals() else None
            location_val = location if 'location' in locals() else None
            
            response = jsonify({
                "error": f"Unexpected error: {str(outer_error)}",
                "platform": platform_val,
                "location": location_val,
                "error_type": "unhandled_exception"
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
        except Exception as final_error:
            # Last resort - return minimal response with CORS
            try:
                response = jsonify({"error": "Internal server error - could not process request"})
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 500
            except:
                # Absolute last resort - this should never happen
                return '{"error":"Internal server error"}', 500, {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}

@app.route('/api/validate-url', methods=['POST', 'GET'])
def validate_url():
    """Validate URL and detect platform without triggering scraper."""
    # Get URL from request (POST body or GET query param)
    if request.is_json and request.json:
        url = request.json.get('url')
        expected_platform = request.json.get('expected_platform')
    else:
        url = request.args.get('url') or (request.form.get('url') if request.form else None)
        expected_platform = request.args.get('expected_platform') or (request.form.get('expected_platform') if request.form else None)
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        return jsonify({
            "error": "Invalid URL format. URL must start with http:// or https://",
            "isValid": False
        }), 400
    
    # Detect platform and route
    platform, table_name, scraper_config, location = TableRouter.route_url(url)
    
    # Validate against expected platform if provided
    if expected_platform and platform != expected_platform:
        return jsonify({
            "platform": platform,
            "table": table_name,
            "location": location,
            "isValid": False,
            "error": f"URL is for {platform or 'unknown platform'}, but expected {expected_platform}"
        }), 400
    
    if not platform or not table_name:
        return jsonify({
            "platform": None,
            "table": None,
            "location": location,
            "isValid": False,
            "error": "Unknown or unsupported platform"
        }), 400
    
    return jsonify({
        "platform": platform,
        "table": table_name,
        "location": location,
        "isValid": True
    })

@app.route('/api/trigger-from-url', methods=['POST', 'GET'])
def trigger_from_url():
    """Trigger scraper from any URL - automatically detects platform and routes to appropriate scraper."""
    # Get URL from request (POST body or GET query param)
    if request.is_json and request.json:
        url = request.json.get('url')
    else:
        url = request.args.get('url') or (request.form.get('url') if request.form else None)
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        return jsonify({"error": "Invalid URL format. URL must start with http:// or https://"}), 400
    
    # Detect platform and route
    platform, table_name, scraper_config, location = TableRouter.route_url(url)
    
    if not platform or not scraper_config:
        # Unknown platform - return error (for now, generic scraper handler can be added later)
        return jsonify({
            "error": "Unknown or unsupported platform",
            "url": url,
            "detected_location": location
        }), 400
    
    # Get status dict based on platform
    status_dict_map = {
        'apartments.com': apartments_scraper_status,
        'hotpads': hotpads_status,
        'redfin': redfin_status,
        'trulia': trulia_status,
        'zillow_fsbo': zillow_fsbo_status,
        'zillow_frbo': zillow_frbo_status,
        'fsbo': scraper_status,
    }
    
    status_dict = status_dict_map.get(platform)
    if not status_dict:
        return jsonify({"error": f"No status tracking for platform: {platform}"}), 500
    
    # Check if scraper is already running
    if status_dict["running"]:
        return jsonify({
            "error": f"Scraper for {platform} is already running",
            "platform": platform,
            "table": table_name
        }), 400
    
    # Map platform to scraper name for logging (use capitalized names for consistency)
    scraper_name_map = {
        'apartments.com': 'Apartments',
        'hotpads': 'Hotpads',
        'redfin': 'Redfin',
        'trulia': 'Trulia',
        'zillow_fsbo': 'Zillow_FSBO',
        'zillow_frbo': 'Zillow_FRBO',
        'fsbo': 'FSBO'
    }
    scraper_name = scraper_name_map.get(platform, platform.title())
    
    # Build command based on scraper config
    scraper_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), scraper_config['scraper_dir'])
    url_param = scraper_config['url_param']
    
    if scraper_config['scraper_name'] == 'forsalebyowner_selenium_scraper':
        # FSBO uses a different command structure - now supports --url argument
        cmd = [sys.executable, scraper_config['command'][0], '--url', url]
        env = None
    else:
        # Scrapy-based scrapers
        cmd = [sys.executable] + scraper_config['command'] + [f"{url_param}={url}"]
        env = None
    
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        run_process_with_logging(cmd, scraper_dir, scraper_name, status_dict, env=env)
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": f"Scraper started for {platform}",
        "platform": platform,
        "table": table_name,
        "url": url,
        "location": location,
        "scraper_config": {
            "scraper_name": scraper_config['scraper_name'],
            "scraper_dir": scraper_config['scraper_dir']
        }
    })

@app.route('/api/trigger-all', methods=['POST', 'GET'])
def trigger_all():
    global all_scrapers_status
    if all_scrapers_status["running"]:
        return jsonify({"error": "All Scrapers job is already running"}), 400
    
    # Start the sequential runner in a background thread
    thread = threading.Thread(target=run_sequential_scrapers)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Started sequential run of all scrapers"})

@app.route('/api/status-all', methods=['GET'])
def get_all_status():
    return jsonify({
        "all_scrapers": {
            "running": all_scrapers_status["running"],
            "last_run": all_scrapers_status["last_run"],
            "finished_at": all_scrapers_status["finished_at"],
            "current_scraper": all_scrapers_status["current_scraper"]
        },
        "fsbo": { "status": "running" if scraper_status["running"] else "idle", "last_run": scraper_status["last_run"], "last_result": scraper_status["last_result"] },
        "apartments": { "status": "running" if apartments_scraper_status["running"] else "idle", "last_run": apartments_scraper_status["last_run"], "last_result": apartments_scraper_status["last_result"] },
        "zillow_fsbo": { "status": "running" if zillow_fsbo_status["running"] else "idle", "last_run": zillow_fsbo_status["last_run"], "last_result": zillow_fsbo_status["last_result"] },
        "zillow_frbo": { "status": "running" if zillow_frbo_status["running"] else "idle", "last_run": zillow_frbo_status["last_run"], "last_result": zillow_frbo_status["last_result"] },
        "hotpads": { "status": "running" if hotpads_status["running"] else "idle", "last_run": hotpads_status["last_run"], "last_result": hotpads_status["last_result"] },
        "redfin": { "status": "running" if redfin_status["running"] else "idle", "last_run": redfin_status["last_run"], "last_result": redfin_status["last_result"] },
        "trulia": { "status": "running" if trulia_status["running"] else "idle", "last_run": trulia_status["last_run"], "last_result": trulia_status["last_result"] },
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get logs from the log buffer, optionally filtered by scraper name"""
    scraper_name = request.args.get('scraper', None)
    limit = request.args.get('limit', type=int)
    
    # Get logs from buffer (most recent first)
    logs = list(LOG_BUFFER)
    
    # Filter by scraper name if provided (logs have format "[scraper_name] message" or contain scraper name)
    if scraper_name:
        # Map platform names to scraper names used in logs
        scraper_name_map = {
            'apartments': 'Apartments',
            'apartments.com': 'Apartments',
            'hotpads': 'Hotpads',
            'redfin': 'Redfin',
            'trulia': 'Trulia',
            'zillow_fsbo': 'Zillow_FSBO',
            'zillow_frbo': 'Zillow_FRBO',
            'fsbo': 'FSBO'
        }
        log_scraper_name = scraper_name_map.get(scraper_name, scraper_name)
        # Filter logs that start with [scraper_name] (strict matching)
        # Only match logs that explicitly start with the scraper name in brackets
        logs = [
            log for log in logs 
            if log["message"].startswith(f"[{log_scraper_name}]")
            or log["message"].startswith(f"[{log_scraper_name.lower()}]")
        ]
    
    # Limit number of logs if specified (most recent)
    # Note: Reverse the list first to get most recent logs, then take limit from the end
    if limit and limit > 0:
        logs = logs[-limit:] if len(logs) > limit else logs
    
    # Reverse to show most recent first (newest at the end of the list)
    logs.reverse()
    
    return jsonify({
        "logs": logs,
        "total": len(logs)
    })

@app.route('/api/stop-scraper', methods=['GET', 'POST'])
def stop_scraper():
    id = request.args.get('id')
    if not id:
        return jsonify({"error": "Missing id"}), 400
    
    # Map friendly IDs to internal names
    id_map = {
        "fsbo": "FSBO",
        "apartments": "Apartments",
        "zillow_fsbo": "Zillow_FSBO",
        "zillow_frbo": "Zillow_FRBO",
        "hotpads": "Hotpads",
        "redfin": "Redfin",
        "trulia": "Trulia"
    }
    
    internal_name = id_map.get(id, id)
    process_found = False
    
    if internal_name in active_processes:
        add_log(f"Stopping {internal_name} requested by user...", "info")
        ensure_process_killed(internal_name)
        process_found = True
    
    # Reset status dictionaries even if process handle was missing
    status_updated = False
    if id == "fsbo":
        if scraper_status["running"]: status_updated = True
        scraper_status["running"] = False
    elif id == "apartments":
        if apartments_scraper_status["running"]: status_updated = True
        apartments_scraper_status["running"] = False
    elif id == "zillow_fsbo":
        if zillow_fsbo_status["running"]: status_updated = True
        zillow_fsbo_status["running"] = False
    elif id == "zillow_frbo":
        if zillow_frbo_status["running"]: status_updated = True
        zillow_frbo_status["running"] = False
    elif id == "hotpads":
        if hotpads_status["running"]: status_updated = True
        hotpads_status["running"] = False
    elif id == "redfin":
        if redfin_status["running"]: status_updated = True
        redfin_status["running"] = False
    elif id == "trulia":
        if trulia_status["running"]: status_updated = True
        trulia_status["running"] = False
        
    if process_found:
        return jsonify({"message": f"Stopped {internal_name}"}), 200
    elif status_updated:
        add_log(f"Reset {internal_name} status (no active process handle found)", "info")
        return jsonify({"message": f"Reset {internal_name} status"}), 200
    
    return jsonify({"error": "Scraper not running"}), 404

@app.route('/api/stop-all', methods=['GET', 'POST'])
def stop_all():
    global stop_all_requested, all_scrapers_status
    if not all_scrapers_status["running"]:
        return jsonify({"error": "No sequential run active"}), 400
    
    stop_all_requested = True
    add_log("🛑 User requested to stop ALL scrapers.", "warning")
    
    # Also stop the current active process if any
    current = all_scrapers_status["current_scraper"]
    if current and current in active_processes:
        ensure_process_killed(current)
        
    return jsonify({"message": "Stop request received for sequential run"}), 200

@app.route('/api/trigger-enrichment', methods=['POST', 'GET'])
def trigger_enrichment():
    if enrichment_status["running"]:
        return jsonify({"error": "Enrichment is already running"}), 400
    
    limit = request.args.get("limit", 50)
    source = request.args.get("source") # Optional priority source
    
    try:
        limit = int(limit)
    except:
        limit = 50
        
    def worker():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        cmd = [sys.executable, "batchdata_worker.py", "--limit", str(limit)]
        if source:
            cmd.extend(["--source", source])
            
        run_process_with_logging(
            cmd,
            base_dir,
            "Enrichment",
            enrichment_status
        )
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    msg = f"Enrichment started with limit {limit}"
    if source:
        msg += f" (Prioritizing {source})"
        
    return jsonify({"message": msg})

@app.route('/api/status-enrichment', methods=['GET'])
def get_enrichment_status():
    return jsonify({
        "status": "running" if enrichment_status["running"] else "idle",
        "last_run": enrichment_status["last_run"],
        "error": enrichment_status["error"]
    })

@app.route('/api/enrichment-stats', methods=['GET'])
def get_enrichment_stats():
    """Return enrichment statistics for dashboard display."""
    try:
        from supabase import create_client
        from dotenv import load_dotenv
        load_dotenv()
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return jsonify({"error": "Database not configured"}), 500
            
        supabase = create_client(url, key)
        
        # Get counts by status from enrichment_state (for queue tracking)
        pending = supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("status", "never_checked") \
            .eq("locked", False) \
            .execute()
            
        enriched_state = supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("status", "enriched") \
            .execute()
            
        no_data = supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("status", "no_owner_data") \
            .execute()
        
        # Count by source_used to show smart skips
        scraped = supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("source_used", "scraped") \
            .execute()
            
        # Only count ACTUAL paid API calls (exclude buggy never_checked entries)
        batchdata = supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("source_used", "batchdata") \
            .neq("status", "never_checked") \
            .execute()
        
        # Get ACTUAL count from property_owners table (source of truth)
        # This is the real number of addresses with owner data
        property_owners_total = supabase.table("property_owners") \
            .select("*", count="exact", head=True) \
            .execute()
        
        return jsonify({
            "pending": pending.count or 0,
            "enriched": enriched_state.count or 0,  # Count from enrichment_state (for queue tracking)
            "enriched_owners": property_owners_total.count or 0,  # ACTUAL count from property_owners table
            "no_data": no_data.count or 0,
            "smart_skipped": scraped.count or 0,
            "api_calls": batchdata.count or 0,
            "is_running": enrichment_status["running"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start scheduler in background (runs all scrapers daily at midnight)
    start_scheduler()
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
