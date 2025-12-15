"""
Simple Flask API server for Railway deployment
Provides endpoints to trigger scraper and check status
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import os
import threading
from datetime import datetime
import sys

app = Flask(__name__)
# Enable CORS for all routes - allows frontend to call backend API
# You can restrict to specific origins if needed: CORS(app, origins=["https://scraperfrontend-production.up.railway.app"])
CORS(app)

# Global status dictionaries
scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
apartments_scraper_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_fsbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
zillow_frbo_status = {"running": False, "last_run": None, "last_result": None, "error": None}
hotpads_status = {"running": False, "last_run": None, "last_result": None, "error": None}
all_scrapers_status = {"running": False, "last_run": None, "last_result": None, "error": None, "current_scraper": None, "completed": []}

# Global process tracker for stopping
active_processes = {}

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
                [sys.executable, "forsalebyowner_selenium_scraper.py"],
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

@app.route('/api/trigger-apartments', methods=['POST'])
def trigger_apartments_scraper():
    """Trigger the apartments scraper"""
    global apartments_scraper_status
    
    if apartments_scraper_status["running"]:
        return jsonify({"error": "Apartments scraper is already running"}), 400
    
    # Get city parameter from request before starting thread (request context not available in thread)
    city = "chicago-il"
    if request.is_json and request.json:
        city = request.json.get("city", city)
    elif request.args:
        city = request.args.get("city", city)
    
    apartments_scraper_status["running"] = True
    apartments_scraper_status["error"] = None
    apartments_scraper_status["last_run"] = datetime.now().isoformat()
    
    def execute_apartments_scraper(city_param):
        try:
            # Get the base directory (where api_server.py is located)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Path to apartments scraper directory (new flattened structure)
            scraper_dir = os.path.join(base_dir, "Apartments_Scraper")
            
            if not os.path.exists(scraper_dir):
                apartments_scraper_status["error"] = f"Scraper directory not found: {scraper_dir}"
                apartments_scraper_status["last_result"] = {
                    "success": False,
                    "error": apartments_scraper_status["error"],
                    "stdout": "",
                    "stderr": apartments_scraper_status["error"],
                    "returncode": 1
                }
                apartments_scraper_status["running"] = False
                return
            
            # Run the apartments scraper using Scrapy
            # The scraper will automatically upload to Supabase via SupabasePipeline
            result = subprocess.run(
                [sys.executable, "-m", "scrapy", "crawl", "apartments_frbo", "-a", f"city={city_param}"],
                cwd=scraper_dir,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            apartments_scraper_status["last_result"] = {
                "success": result.returncode == 0,
                "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
                "stderr": result.stderr[-1000:] if result.stderr else "",  # Last 1000 chars
                "returncode": result.returncode,
                "city": city_param
            }
            
            if result.returncode != 0:
                apartments_scraper_status["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            apartments_scraper_status["error"] = "Apartments scraper timed out after 1 hour"
            apartments_scraper_status["last_result"] = {
                "success": False,
                "error": "Timeout",
                "stdout": "",
                "stderr": "Scraper timed out after 1 hour",
                "returncode": -1
            }
        except Exception as e:
            apartments_scraper_status["error"] = str(e)
            apartments_scraper_status["last_result"] = {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }
        finally:
            apartments_scraper_status["running"] = False
    
    # Start scraper in background thread
    thread = threading.Thread(target=execute_apartments_scraper, args=(city,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Apartments scraper started",
        "started_at": apartments_scraper_status["last_run"],
        "city": city,
        "note": "Scraper will automatically upload results to Supabase"
    })

@app.route('/api/trigger-apartments', methods=['GET'])
def trigger_apartments_scraper_get():
    """Trigger the apartments scraper via GET (for easy testing)"""
    return trigger_apartments_scraper()

@app.route('/api/status-apartments', methods=['GET'])
def get_apartments_status():
    """Get apartments scraper status"""
    return jsonify({
        "status": "running" if apartments_scraper_status["running"] else "idle",
        "last_run": apartments_scraper_status["last_run"],
        "last_result": apartments_scraper_status["last_result"],
        "error": apartments_scraper_status["error"],
        "timestamp": datetime.now().isoformat()
    })

# ============================================================
# Zillow FSBO Scraper
# ============================================================
@app.route('/api/trigger-zillow-fsbo', methods=['GET', 'POST'])
def trigger_zillow_fsbo():
    """Trigger the Zillow FSBO scraper"""
    global zillow_fsbo_status
    
    if zillow_fsbo_status["running"]:
        return jsonify({"error": "Zillow FSBO scraper is already running"}), 400
    
    # Get URL from request
    start_url = None
    if request.is_json and request.json:
        start_url = request.json.get("url")
    elif request.args:
        start_url = request.args.get("url")
    
    zillow_fsbo_status["running"] = True
    zillow_fsbo_status["error"] = None
    zillow_fsbo_status["last_run"] = datetime.now().isoformat()
    
    def execute_zillow_fsbo(url_param):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            scraper_dir = os.path.join(base_dir, "Zillow_FSBO_Scraper")
            
            if not os.path.exists(scraper_dir):
                zillow_fsbo_status["error"] = f"Directory not found: {scraper_dir}"
                zillow_fsbo_status["last_result"] = {"success": False, "error": zillow_fsbo_status["error"]}
                zillow_fsbo_status["running"] = False
                return
            
            cmd = [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"]
            if url_param:
                cmd.extend(["-a", f"start_url={url_param}"])
            
            result = subprocess.run(
                cmd,
                cwd=scraper_dir,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            zillow_fsbo_status["last_result"] = {
                "success": result.returncode == 0,
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "returncode": result.returncode
            }
            
            if result.returncode != 0:
                zillow_fsbo_status["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            zillow_fsbo_status["error"] = "Scraper timed out after 1 hour"
            zillow_fsbo_status["last_result"] = {"success": False, "error": "Timeout"}
        except Exception as e:
            zillow_fsbo_status["error"] = str(e)
            zillow_fsbo_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            zillow_fsbo_status["running"] = False
    
    thread = threading.Thread(target=execute_zillow_fsbo, args=(start_url,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Zillow FSBO scraper started",
        "started_at": zillow_fsbo_status["last_run"],
        "url_used": start_url or "Default"
    })

@app.route('/api/status-zillow-fsbo', methods=['GET'])
def get_zillow_fsbo_status():
    """Get Zillow FSBO scraper status"""
    return jsonify({
        "status": "running" if zillow_fsbo_status["running"] else "idle",
        "last_run": zillow_fsbo_status["last_run"],
        "last_result": zillow_fsbo_status["last_result"],
        "error": zillow_fsbo_status["error"],
        "timestamp": datetime.now().isoformat()
    })

# ============================================================
# Zillow FRBO Scraper
# ============================================================
@app.route('/api/trigger-zillow-frbo', methods=['GET', 'POST'])
def trigger_zillow_frbo():
    """Trigger the Zillow FRBO scraper"""
    global zillow_frbo_status
    
    if zillow_frbo_status["running"]:
        return jsonify({"error": "Zillow FRBO scraper is already running"}), 400
    
    # Get URL from request
    start_url = None
    if request.is_json and request.json:
        start_url = request.json.get("url")
    elif request.args:
        start_url = request.args.get("url")
    
    zillow_frbo_status["running"] = True
    zillow_frbo_status["error"] = None
    zillow_frbo_status["last_run"] = datetime.now().isoformat()
    
    def execute_zillow_frbo(url_param):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            scraper_dir = os.path.join(base_dir, "Zillow_FRBO_Scraper")
            
            if not os.path.exists(scraper_dir):
                zillow_frbo_status["error"] = f"Directory not found: {scraper_dir}"
                zillow_frbo_status["last_result"] = {"success": False, "error": zillow_frbo_status["error"]}
                zillow_frbo_status["running"] = False
                return
            
            cmd = [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"]
            if url_param:
                cmd.extend(["-a", f"start_url={url_param}"])
            
            proc = subprocess.Popen(
                cmd,
                cwd=scraper_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Register process
            active_processes['zillow_frbo'] = proc
            
            stdout, stderr = proc.communicate(timeout=3600)
            
            # Unregister
            if 'zillow_frbo' in active_processes:
                del active_processes['zillow_frbo']
            
            zillow_frbo_status["last_result"] = {
                "success": proc.returncode == 0,
                "stdout": stdout[-1000:] if stdout else "",
                "stderr": stderr[-1000:] if stderr else "",
                "returncode": proc.returncode
            }
            
            if proc.returncode != 0:
                zillow_frbo_status["error"] = stderr[-500:] if stderr else "Unknown error"
            
            # Check if was stopped manually (returncode might be non-zero or specific signal)
            if proc.returncode != 0 and "Terminated" in (stderr or ""):
                 zillow_frbo_status["last_result"]["error"] = "Stopped by user"
            
        except subprocess.TimeoutExpired:
            # If timeout, terminate the process
            if 'zillow_frbo' in active_processes:
                active_processes['zillow_frbo'].terminate()
                del active_processes['zillow_frbo']
            zillow_frbo_status["error"] = "Scraper timed out after 1 hour"
            zillow_frbo_status["last_result"] = {"success": False, "error": "Timeout"}
        except Exception as e:
            if 'zillow_frbo' in active_processes:
                del active_processes['zillow_frbo']
            zillow_frbo_status["error"] = str(e)
            zillow_frbo_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            zillow_frbo_status["running"] = False
    
    thread = threading.Thread(target=execute_zillow_frbo, args=(start_url,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Zillow FRBO scraper started",
        "started_at": zillow_frbo_status["last_run"],
        "url_used": start_url or "Default"
    })

@app.route('/api/status-zillow-frbo', methods=['GET'])
def get_zillow_frbo_status():
    """Get Zillow FRBO scraper status"""
    return jsonify({
        "status": "running" if zillow_frbo_status["running"] else "idle",
        "last_run": zillow_frbo_status["last_run"],
        "last_result": zillow_frbo_status["last_result"],
        "error": zillow_frbo_status["error"],
        "timestamp": datetime.now().isoformat()
    })

# ============================================================
# Hotpads Scraper
# ============================================================
@app.route('/api/trigger-hotpads', methods=['GET', 'POST'])
def trigger_hotpads():
    """Trigger the Hotpads scraper"""
    global hotpads_status
    
    if hotpads_status["running"]:
        return jsonify({"error": "Hotpads scraper is already running"}), 400
    
    hotpads_status["running"] = True
    hotpads_status["error"] = None
    hotpads_status["last_run"] = datetime.now().isoformat()
    
    def execute_hotpads():
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            scraper_dir = os.path.join(base_dir, "Hotpads_Scraper")
            
            if not os.path.exists(scraper_dir):
                hotpads_status["error"] = f"Directory not found: {scraper_dir}"
                hotpads_status["last_result"] = {"success": False, "error": hotpads_status["error"]}
                hotpads_status["running"] = False
                return
            
            result = subprocess.run(
                [sys.executable, "-m", "scrapy", "crawl", "hotpads_scraper"],
                cwd=scraper_dir,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            hotpads_status["last_result"] = {
                "success": result.returncode == 0,
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "returncode": result.returncode
            }
            
            if result.returncode != 0:
                hotpads_status["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            hotpads_status["error"] = "Scraper timed out after 1 hour"
            hotpads_status["last_result"] = {"success": False, "error": "Timeout"}
        except Exception as e:
            hotpads_status["error"] = str(e)
            hotpads_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            hotpads_status["running"] = False
    
    thread = threading.Thread(target=execute_hotpads)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Hotpads scraper started",
        "started_at": hotpads_status["last_run"]
    })

@app.route('/api/status-hotpads', methods=['GET'])
def get_hotpads_status():
    """Get Hotpads scraper status"""
    return jsonify({
        "status": "running" if hotpads_status["running"] else "idle",
        "last_run": hotpads_status["last_run"],
        "last_result": hotpads_status["last_result"],
        "error": hotpads_status["error"],
        "timestamp": datetime.now().isoformat()
    })

# ============================================================
# Run All Scrapers (Sequential)
# ============================================================
@app.route('/api/trigger-all', methods=['GET', 'POST'])
def trigger_all_scrapers():
    """Trigger ALL scrapers sequentially"""
    global all_scrapers_status
    
    if all_scrapers_status["running"]:
        return jsonify({
            "error": "All scrapers job is already running",
            "current_scraper": all_scrapers_status["current_scraper"]
        }), 400
    
    all_scrapers_status["running"] = True
    all_scrapers_status["error"] = None
    all_scrapers_status["last_run"] = datetime.now().isoformat()
    all_scrapers_status["current_scraper"] = None
    all_scrapers_status["completed"] = []
    
    def execute_all_scrapers():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        scrapers = [
            {"name": "fsbo", "cmd": [sys.executable, "forsalebyowner_selenium_scraper.py"], "cwd": base_dir},
            {"name": "apartments", "cmd": [sys.executable, "-m", "scrapy", "crawl", "apartments_frbo"], "cwd": os.path.join(base_dir, "Apartments_Scraper")},
            {"name": "zillow_fsbo", "cmd": [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"], "cwd": os.path.join(base_dir, "Zillow_FSBO_Scraper")},
            {"name": "zillow_frbo", "cmd": [sys.executable, "-m", "scrapy", "crawl", "zillow_spider"], "cwd": os.path.join(base_dir, "Zillow_FRBO_Scraper")},
            {"name": "hotpads", "cmd": [sys.executable, "-m", "scrapy", "crawl", "hotpads_scraper"], "cwd": os.path.join(base_dir, "Hotpads_Scraper")}
        ]
        
        for scraper in scrapers:
            try:
                all_scrapers_status["current_scraper"] = scraper["name"]
                
                if not os.path.exists(scraper["cwd"]):
                    all_scrapers_status["completed"].append({
                        "name": scraper["name"],
                        "success": False,
                        "error": f"Directory not found: {scraper['cwd']}"
                    })
                    continue
                
                result = subprocess.run(
                    scraper["cmd"],
                    cwd=scraper["cwd"],
                    capture_output=True,
                    text=True,
                    timeout=3600
                )
                
                all_scrapers_status["completed"].append({
                    "name": scraper["name"],
                    "success": result.returncode == 0,
                    "returncode": result.returncode
                })
                
            except subprocess.TimeoutExpired:
                all_scrapers_status["completed"].append({
                    "name": scraper["name"],
                    "success": False,
                    "error": "Timeout after 1 hour"
                })
            except Exception as e:
                all_scrapers_status["completed"].append({
                    "name": scraper["name"],
                    "success": False,
                    "error": str(e)
                })
        
        all_scrapers_status["current_scraper"] = None
        all_scrapers_status["running"] = False
    
    thread = threading.Thread(target=execute_all_scrapers)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "All scrapers started (running sequentially)",
        "started_at": all_scrapers_status["last_run"],
        "scrapers": ["fsbo", "apartments", "zillow_fsbo", "zillow_frbo", "hotpads"]
    })

@app.route('/api/status-all', methods=['GET'])
def get_all_status():
    """Get status of all scrapers"""
    return jsonify({
        "all_scrapers": {
            "running": all_scrapers_status["running"],
            "last_run": all_scrapers_status["last_run"],
            "current_scraper": all_scrapers_status["current_scraper"],
            "completed": all_scrapers_status["completed"]
        },
        "fsbo": {
            "status": "running" if scraper_status["running"] else "idle",
            "last_run": scraper_status["last_run"]
        },
        "apartments": {
            "status": "running" if apartments_scraper_status["running"] else "idle",
            "last_run": apartments_scraper_status["last_run"]
        },
        "zillow_fsbo": {
            "status": "running" if zillow_fsbo_status["running"] else "idle",
            "last_run": zillow_fsbo_status["last_run"]
        },
        "zillow_frbo": {
            "status": "running" if zillow_frbo_status["running"] else "idle",
            "last_run": zillow_frbo_status["last_run"]
        },
        "hotpads": {
            "status": "running" if hotpads_status["running"] else "idle",
            "last_run": hotpads_status["last_run"]
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/stop-scraper', methods=['GET', 'POST'])
def stop_scraper():
    """Stop a running scraper by ID"""
    scraper_id = request.args.get('id') or (request.json.get('id') if request.is_json else None)
    
    if not scraper_id:
        return jsonify({"error": "Missing scraper id"}), 400
        
    proc = active_processes.get(scraper_id)
    if proc:
        try:
            proc.terminate()
            # Wait a bit or let communicate handle it
            return jsonify({"message": f"Scraper {scraper_id} stopping..."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Scraper not running"}), 404

if __name__ == '__main__':
    # Get port from environment variable or use default 8080
    port = int(os.environ.get('PORT', 8080))
    # Run on 0.0.0.0 to accept connections from outside
    app.run(host='0.0.0.0', port=port, debug=False)
