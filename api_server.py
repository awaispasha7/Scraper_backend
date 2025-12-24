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

app = Flask(__name__)
# Enable CORS for all routes - allows frontend to call backend API
CORS(app)

# Global status dictionaries
scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
apartments_scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_fsbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_frbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
hotpads_status = {"running": False, "last_run": None, "last_result": None, "error": None}
redfin_status = {"running": False, "last_run": None, "last_result": None, "error": None}
trulia_status = {"running": False, "last_run": None, "last_result": None, "error": None}
all_scrapers_status = {"running": False, "last_run": None, "last_result": None, "error": None, "current_scraper": None, "completed": []}

# Global process tracker for stopping
active_processes = {}
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

def run_process_with_logging(cmd, cwd, scraper_name, status_dict):
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
            universal_newlines=True
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
        
        result_info = {
            "success": success,
            "returncode": returncode,
            "timestamp": datetime.now().isoformat()
        }
        status_dict["last_result"] = result_info
        
        if success:
            add_log(f"{scraper_name} completed successfully.", "success")
        else:
            msg = f"{scraper_name} failed with return code {returncode}."
            add_log(msg, "error")
            status_dict["error"] = msg
            
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

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "ForSaleByOwner Scraper API",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get logs, optionally filtering by query param 'since' (timestamp)"""
    since = request.args.get('since')
    if since:
        filtered = [l for l in LOG_BUFFER if l['timestamp'] > since]
        return jsonify(filtered)
    return jsonify(LOG_BUFFER)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": "running" if scraper_status["running"] else "idle",
        "last_run": scraper_status["last_run"],
        "error": scraper_status["error"]
    })

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

if __name__ == '__main__':
    # Start scheduler in background
    start_scheduler()
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
