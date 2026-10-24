import os
import sys
import time
import random
import shutil
import tempfile
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
CONCURRENT_WORKERS = int(os.getenv("CONCURRENT_WORKERS", "1"))
WATCH_MIN_SEC = int(os.getenv("WATCH_MIN_SEC", "35"))
WATCH_MAX_SEC = int(os.getenv("WATCH_MAX_SEC", "55"))
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")

raw_proxies = os.getenv("PROXIES", "")
PROXIES = [p.strip() for p in raw_proxies.split(",") if p.strip()]

PORT = int(os.getenv("PORT", "8080"))
# ----------------------------------------------------------------------

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
    def do_HEAD(self):
        try:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
        except Exception:
            pass

    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with stats_lock:
                import json
                response = json.dumps(stats, indent=2)
            self.wfile.write(response.encode("utf-8"))
        except Exception:
            pass

    def log_message(self, format, *args):
        return


def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), SimpleHealthHandler)
        print(f"[Railway] Healthcheck server listening on 0.0.0.0:{PORT}...", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"[Railway] Health server warning: {e}", flush=True)


def get_chrome_driver(temp_dir: str):
    options = Options()
    options.add_argument(f"--user-data-dir={temp_dir}")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Low-RAM & Cloud Container Stability (Prevents DevToolsActivePort & OOM crashes)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")
    options.add_argument("--blink-settings=imagesEnabled=false")

    # Locate Chrome / Chromium binary on Linux
    chrome_binary = os.getenv("CHROME_BIN", "")
    if not chrome_binary:
        for p in ["/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
            if os.path.exists(p):
                chrome_binary = p
                break
    if chrome_binary and os.path.exists(chrome_binary):
        options.binary_location = chrome_binary

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

    if PROXIES:
        proxy = random.choice(PROXIES)
        options.add_argument(f"--proxy-server={proxy}")

    # Check for local Linux chromedriver
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "")
    if not chromedriver_path and os.path.exists("/usr/bin/chromedriver"):
        chromedriver_path = "/usr/bin/chromedriver"

    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)
    else:
        return webdriver.Chrome(options=options)


def view_task(view_number: int):
    temp_dir = tempfile.mkdtemp(prefix=f"yt_viewer_{view_number}_")
    driver = None
    
    with stats_lock:
        stats["active_workers"] += 1

    try:
        time.sleep(random.uniform(1.0, 3.0))

        driver = get_chrome_driver(temp_dir)

        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            })
        except Exception:
            pass

        print(f"[View #{view_number}] Opening video: {VIDEO_URL}", flush=True)
        driver.get(VIDEO_URL)
        time.sleep(4)

        try:
            consent_btn = driver.find_element(
                By.XPATH, 
                "//button[contains(@aria-label, 'Accept') or contains(@aria-label, 'Reject') or contains(., 'Accept all') or contains(., 'I agree')]"
            )
            consent_btn.click()
            time.sleep(1)
        except Exception:
            pass

        try:
            play_btn = driver.find_element(By.CSS_SELECTOR, "button.ytp-play-button")
            btn_state = play_btn.get_attribute("title") or play_btn.get_attribute("aria-label") or ""
            if "Play" in btn_state:
                play_btn.click()
        except Exception:
            pass

        try:
            driver.execute_script("""
                const v = document.querySelector('video');
                if (v && v.paused) { v.play(); }
            """)
        except Exception:
            pass

        watch_duration = random.randint(WATCH_MIN_SEC, WATCH_MAX_SEC)
        print(f"[View #{view_number}] Watching for {watch_duration}s...", flush=True)
        time.sleep(watch_duration)
        
        with stats_lock:
            stats["completed_views"] += 1
        print(f"[View #{view_number}] View completed! Total completed: {stats['completed_views']}", flush=True)

    except Exception as e:
        print(f"[View #{view_number}] Error: {e}", flush=True)
        traceback.print_exc()
    finally:
        with stats_lock:
            stats["active_workers"] = max(0, stats["active_workers"] - 1)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def main():
    print(f"=== YouTube Viewer Bot (Railway Ready) ===", flush=True)
    print(f"Video URL: {VIDEO_URL}", flush=True)
    print(f"Target Views: {TARGET_VIEWS}", flush=True)
    print(f"Concurrent Workers: {CONCURRENT_WORKERS}", flush=True)
    print(f"Proxies configured: {len(PROXIES)}", flush=True)
    print(f"==========================================\n", flush=True)

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        futures = [executor.submit(view_task, i + 1) for i in range(TARGET_VIEWS)]
        for f in futures:
            try:
                f.result()
            except Exception as ex:
                print(f"Worker task error: {ex}", flush=True)

    print("All view tasks completed.", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
