import os
import sys
import time
import random
import shutil
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Enable UTF-8 encoding for console logs
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------- CONFIGURATION (Railway Env Overrides) ----------------
VIDEO_URL = os.getenv("VIDEO_URL", "https://www.youtube.com/shorts/eTSipzkBEpQ")
TARGET_VIEWS = int(os.getenv("TARGET_VIEWS", "1000"))
CONCURRENT_WORKERS = int(os.getenv("CONCURRENT_WORKERS", "2"))  # 2-3 recommended for cloud containers
WATCH_MIN_SEC = int(os.getenv("WATCH_MIN_SEC", "35"))
WATCH_MAX_SEC = int(os.getenv("WATCH_MAX_SEC", "55"))
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")

# Proxies can be comma-separated in Railway ENV, e.g. "ip:port,user:pass@ip:port"
raw_proxies = os.getenv("PROXIES", "")
PROXIES = [p.strip() for p in raw_proxies.split(",") if p.strip()]

PORT = int(os.getenv("PORT", "8080"))
# ----------------------------------------------------------------------

# Global stats for Railway healthcheck / status web page
stats = {
    "completed_views": 0,
    "active_workers": 0,
    "target_views": TARGET_VIEWS,
    "video_url": VIDEO_URL,
    "started_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
}
stats_lock = threading.Lock()


class SimpleHealthHandler(BaseHTTPRequestHandler):
    """Responds to Railway HTTP healthchecks so the service stays active and healthy."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        with stats_lock:
            import json
            response = json.dumps(stats, indent=2)
        self.wfile.write(response.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress noisy healthcheck logs in Railway console
        return


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHealthHandler)
    print(f"[Railway] Healthcheck server listening on port {PORT}...", flush=True)
    server.serve_forever()


def view_task(view_number: int):
    temp_dir = tempfile.mkdtemp(prefix=f"yt_viewer_{view_number}_")
    driver = None
    
    with stats_lock:
        stats["active_workers"] += 1

    try:
        options = Options()
        options.add_argument(f"--user-data-dir={temp_dir}")
        options.add_argument("--mute-audio")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Essential for Linux / Docker containers on Railway
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        if HEADLESS:
            options.add_argument("--headless=new")
            options.add_argument("--autoplay-policy=no-user-gesture-required")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--window-size=1280,720")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            )
        else:
            options.add_argument("--window-size=640,480")

        # Save bandwidth and CPU inside cloud container
        options.add_argument("--blink-settings=imagesEnabled=false")

        # Assign proxy if provided
        if PROXIES:
            proxy = random.choice(PROXIES)
            options.add_argument(f"--proxy-server={proxy}")

        # Stagger browser launches slightly to avoid CPU spikes
        time.sleep(random.uniform(1.0, 3.0))

        driver = webdriver.Chrome(options=options)

        # Remove navigator.webdriver detection flag via CDP
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })

        print(f"[View #{view_number}] Opening video: {VIDEO_URL}", flush=True)
        driver.get(VIDEO_URL)
        time.sleep(4)

        # 1. Dismiss YouTube cookie / consent prompt if present
        try:
            consent_btn = driver.find_element(
                By.XPATH, 
                "//button[contains(@aria-label, 'Accept') or contains(@aria-label, 'Reject') or contains(., 'Accept all') or contains(., 'I agree')]"
            )
            consent_btn.click()
            time.sleep(1)
        except Exception:
            pass

        # 2. Check and start playback for standard videos or Shorts
        try:
            play_btn = driver.find_element(By.CSS_SELECTOR, "button.ytp-play-button")
            btn_state = play_btn.get_attribute("title") or play_btn.get_attribute("aria-label") or ""
            if "Play" in btn_state:
                play_btn.click()
        except Exception:
            pass

        # For shorts, ensure video element is unpaused and playing
        try:
            driver.execute_script("""
                const v = document.querySelector('video');
                if (v && v.paused) { v.play(); }
            """)
        except Exception:
            pass

        # 3. Watch duration
        watch_duration = random.randint(WATCH_MIN_SEC, WATCH_MAX_SEC)
        print(f"[View #{view_number}] Watching for {watch_duration}s...", flush=True)
        time.sleep(watch_duration)
        
        with stats_lock:
            stats["completed_views"] += 1
        print(f"[View #{view_number}] View completed successfully! Total views: {stats['completed_views']}", flush=True)

    except Exception as e:
        print(f"[View #{view_number}] Error: {e}", flush=True)
    finally:
        with stats_lock:
            stats["active_workers"] = max(0, stats["active_workers"] - 1)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        # Clean up temporary profile folder to keep disk clean
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def main():
    print(f"=== YouTube Viewer Bot ===", flush=True)
    print(f"Video URL: {VIDEO_URL}", flush=True)
    print(f"Target Views: {TARGET_VIEWS}", flush=True)
    print(f"Concurrent Workers: {CONCURRENT_WORKERS}", flush=True)
    print(f"Proxies configured: {len(PROXIES)}", flush=True)
    print(f"==========================\n", flush=True)

    # Start healthcheck HTTP server in background thread for Railway
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        futures = [executor.submit(view_task, i + 1) for i in range(TARGET_VIEWS)]
        for f in futures:
            try:
                f.result()
            except Exception as ex:
                print(f"Task exception: {ex}", flush=True)

    print("All view tasks completed.", flush=True)
    # Keep server alive to inspect final status
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
