"""
Stock Checker for Target - Optimized for speed.
Fast HTTP checks with browser fallback. Parallel URL monitoring.
"""

import json
import os
import re
import time
import sys
import winsound
import threading
import logging
import concurrent.futures

import requests

try:
    from plyer import notification
except ImportError:
    notification = None

from playwright.sync_api import sync_playwright


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
LOG_PATH = os.path.join(SCRIPT_DIR, "stock_checker.log")

TARGET_IN_STOCK_SELECTORS = [
    'button[data-test="addToCartButton"]',
    'button[data-test="shipItButton"]',
    'button[data-test="pickItUpButton"]',
]

TARGET_OUT_OF_STOCK_INDICATORS = [
    "out of stock",
    "sold out",
    "notify me when it's back",
    "currently unavailable",
]

BLOCKED_RESOURCE_TYPES = ["image", "media", "font", "stylesheet"]
BLOCKED_URL_PATTERNS = [
    "analytics", "tracking", "ads", "doubleclick", "facebook",
    "google-analytics", "hotjar", "optimizely", "segment",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
]

SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# --- Config ---

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    else:
        config = {"interval_seconds": 5, "urls": []}

    config.setdefault("interval_seconds", 5)
    config.setdefault("urls", [])
    return config


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


# --- Logging ---

def setup_logging():
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def log(message: str):
    logging.info(message)


# --- Helpers ---

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_short_name(url: str) -> str:
    try:
        if "/p/" in url:
            name = url.split("/p/")[1].split("/")[0]
            return name.replace("-", " ").title()
    except Exception:
        pass
    return url[:50]


def get_tcin(url: str) -> str:
    """Extract Target product TCIN from URL."""
    match = re.search(r"A-(\d+)", url)
    return match.group(1) if match else ""


# --- Fast HTTP Check ---

def check_stock_fast(url: str, session: requests.Session) -> tuple[bool, str, bool]:
    """
    Fast stock check using HTTP request (no browser).
    Returns (is_in_stock, reason, is_conclusive).
    If not conclusive, caller should fall back to browser check.
    """
    try:
        resp = session.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        return False, f"HTTP error: {e}", False

    html = resp.text.lower()

    # Check for out-of-stock indicators in raw HTML
    for phrase in TARGET_OUT_OF_STOCK_INDICATORS:
        if phrase in html:
            return False, f"'{phrase}'", True

    # Look for add-to-cart button in HTML
    if 'data-test="addtocartbutton"' in html or 'data-test="addToCartButton"' in resp.text:
        return True, "Add to cart button found (fast)", True

    if 'data-test="shipitbutton"' in html or 'data-test="shipItButton"' in resp.text:
        return True, "Ship it button found (fast)", True

    if 'data-test="pickitupbutton"' in html or 'data-test="pickItUpButton"' in resp.text:
        return True, "Pick it up button found (fast)", True

    # Try to find product data in embedded JSON (__NEXT_DATA__ or similar)
    try:
        next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if next_data_match:
            data = json.loads(next_data_match.group(1))
            data_str = json.dumps(data).lower()

            if '"out_of_stock"' in data_str or '"unavailable"' in data_str:
                return False, "API data: out of stock", True

            if '"in_stock"' in data_str or '"available"' in data_str:
                return True, "API data: in stock!", True
    except Exception:
        pass

    # Try Target's fulfillment info in page
    try:
        tcin = get_tcin(url)
        if tcin:
            # Look for availability in any embedded JSON
            avail_patterns = [
                rf'"tcin":"{tcin}".*?"availability_status":"([^"]+)"',
                r'"availability_status":"([^"]+)"',
                r'"available_to_promise_quantity":(\d+)',
            ]
            for pattern in avail_patterns:
                match = re.search(pattern, resp.text, re.DOTALL)
                if match:
                    val = match.group(1)
                    if val in ("OUT_OF_STOCK", "UNAVAILABLE"):
                        return False, f"Status: {val}", True
                    elif val in ("IN_STOCK", "AVAILABLE", "LIMITED_STOCK"):
                        return True, f"Status: {val}!", True
                    elif val.isdigit() and int(val) > 0:
                        return True, f"Quantity available: {val}!", True
    except Exception:
        pass

    # Not conclusive - need browser check
    return False, "Inconclusive (fast check)", False


# --- Browser Check (fallback) ---

def check_stock_browser(page, url: str) -> tuple[bool, str]:
    """
    Full browser check - slower but handles JS-rendered content.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        return False, f"Page load error: {e}"

    # Wait for any add-to-cart button (max 4 seconds)
    for selector in TARGET_IN_STOCK_SELECTORS:
        try:
            element = page.wait_for_selector(selector, timeout=2000, state="visible")
            if element:
                button_text = element.inner_text().strip()
                return True, f"Found: '{button_text}'"
        except Exception:
            continue

    # Check page text
    try:
        page_text = page.inner_text("body").lower()
    except Exception:
        return False, "Could not read page"

    for phrase in TARGET_OUT_OF_STOCK_INDICATORS:
        if phrase in page_text:
            return False, f"'{phrase}'"

    # Last resort: check all buttons
    try:
        buttons = page.query_selector_all("button")
        for btn in buttons:
            try:
                txt = btn.inner_text().strip().lower()
                if "add to cart" in txt and btn.is_visible():
                    return True, "Found 'add to cart' button"
            except Exception:
                continue
    except Exception:
        pass

    return False, "No add-to-cart button"


# --- Monitor Display ---

class StatusMonitor:
    def __init__(self, num_urls: int):
        self.start_time = time.time()
        self.total_checks = 0
        self.current_activity = "Starting..."
        self.last_results = {}  # url -> result string
        self.state = "idle"
        self.next_check_at = 0
        self._spinner_idx = 0
        self._running = True
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _get_uptime(self) -> str:
        elapsed = int(time.time() - self.start_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _run(self):
        while self._running:
            with self._lock:
                self._render()
            time.sleep(0.15)

    def _render(self):
        spinner = SPINNER_CHARS[self._spinner_idx % len(SPINNER_CHARS)]
        self._spinner_idx += 1
        uptime = self._get_uptime()

        if self.state == "checking":
            status = f"{spinner} CHECKING..."
        elif self.state == "waiting":
            remaining = max(0, int(self.next_check_at - time.time()))
            status = f"{spinner} Next in {remaining}s"
        else:
            status = f"{spinner} Starting..."

        line = (
            f"\r  {status} | "
            f"Uptime: {uptime} | "
            f"Checks: {self.total_checks} | "
            f"{self.current_activity}"
        )
        sys.stdout.write(f"{line:<130}")
        sys.stdout.flush()

    def set_checking(self, activity: str = ""):
        with self._lock:
            self.state = "checking"
            if activity:
                self.current_activity = activity

    def set_waiting(self, interval: int):
        with self._lock:
            self.state = "waiting"
            self.next_check_at = time.time() + interval

    def set_result(self, url: str, result: str):
        with self._lock:
            self.total_checks += 1
            name = get_short_name(url)[:20]
            self.last_results[url] = result
            self.current_activity = f"[{name}] {result}"

    def stop(self):
        self._running = False

    def clear_line(self):
        sys.stdout.write("\r" + " " * 130 + "\r")
        sys.stdout.flush()


# --- Menu ---

def show_menu(config: dict):
    clear_screen()
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║            TARGET STOCK CHECKER  v2.0                 ║")
    print("  ╠═══════════════════════════════════════════════════════╣")
    print("  ║                                                       ║")
    print(f"  ║   Check every: {config['interval_seconds']} second(s){' ' * (34 - len(str(config['interval_seconds'])))}║")
    print(f"  ║   Method: Fast HTTP + Browser fallback                ║")
    print("  ║                                                       ║")
    print("  ║   Products being monitored:                           ║")

    if config["urls"]:
        for i, url in enumerate(config["urls"]):
            name = get_short_name(url)
            tcin = get_tcin(url)
            display = f"{name} (A-{tcin})" if tcin else name
            print(f"  ║   {i+1}. {display:<49} ║")
    else:
        print("  ║   (none added yet)                                    ║")

    print("  ║                                                       ║")
    print("  ╠═══════════════════════════════════════════════════════╣")
    print("  ║   OPTIONS:                                            ║")
    print("  ║   1. Add a product URL                                ║")
    print("  ║   2. Remove a product                                 ║")
    print("  ║   3. Change check interval                            ║")
    print("  ║   4. START monitoring                                 ║")
    print("  ║   5. View log (last 30 entries)                       ║")
    print("  ║   6. Clear log                                        ║")
    print("  ║   7. Test alert sound                                 ║")
    print("  ║   8. Exit                                             ║")
    print("  ║                                                       ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()


def menu_add_url(config: dict):
    print()
    print("  Paste the Target product URL below:")
    print("  (example: https://www.target.com/p/product-name/-/A-12345678)")
    url = input("\n  > ").strip()
    if url:
        if "target.com" in url:
            tcin = get_tcin(url)
            if tcin:
                config["urls"].append(url)
                save_config(config)
                name = get_short_name(url)
                print(f"\n  Added: {name} (A-{tcin})")
            else:
                print("\n  Could not find product ID (A-XXXXXXXX) in URL.")
                print("  Make sure the URL contains something like /-/A-95082138")
        else:
            print("\n  That doesn't look like a Target URL.")
    else:
        print("\n  No URL entered.")
    input("\n  Press Enter to go back...")


def menu_remove_url(config: dict):
    if not config["urls"]:
        print("\n  No products to remove.")
        input("\n  Press Enter to go back...")
        return

    print()
    print("  Which product do you want to remove?")
    for i, url in enumerate(config["urls"]):
        name = get_short_name(url)
        print(f"  {i+1}. {name}")
    print(f"  0. Cancel")

    try:
        choice = int(input("\n  Enter number: ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(config["urls"]):
            removed = config["urls"].pop(choice - 1)
            save_config(config)
            print(f"\n  Removed: {get_short_name(removed)}")
        else:
            print("\n  Invalid number.")
    except ValueError:
        print("\n  Invalid input.")

    input("\n  Press Enter to go back...")


def menu_change_interval(config: dict):
    print()
    print(f"  Current interval: {config['interval_seconds']} second(s)")
    print()
    print("  How often should it check? (in seconds)")
    print("  1 = fastest (aggressive), 3 = fast, 5 = balanced, 10 = safe")
    print()
    print("  WARNING: 1-2 seconds is very aggressive and may get blocked.")

    try:
        val = int(input("\n  Enter seconds: ").strip())
        if val < 1:
            val = 1
        config["interval_seconds"] = val
        save_config(config)
        print(f"\n  Interval set to {val} second(s).")
    except ValueError:
        print("\n  Invalid input. Enter a number.")

    input("\n  Press Enter to go back...")


def menu_view_log():
    clear_screen()
    print()
    if not os.path.exists(LOG_PATH):
        print("  No log file yet. Start monitoring first.")
        input("\n  Press Enter to go back...")
        return

    print("  ═══ LAST 30 LOG ENTRIES ═══")
    print()

    with open(LOG_PATH, "r") as f:
        lines = f.readlines()

    last_lines = lines[-30:] if len(lines) > 30 else lines
    for line in last_lines:
        # Highlight IN STOCK entries
        text = line.rstrip()
        if "IN STOCK" in text:
            print(f"  >>> {text}")
        else:
            print(f"  {text}")

    print()
    print(f"  (Total log entries: {len(lines)})")
    print(f"  Log file: {LOG_PATH}")
    input("\n  Press Enter to go back...")


def menu_clear_log():
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
        setup_logging()
        print("\n  Log cleared.")
    else:
        print("\n  No log file to clear.")
    input("\n  Press Enter to go back...")


def menu_test_alert():
    print("\n  Playing alert sound...")
    for _ in range(3):
        winsound.Beep(1000, 400)
        time.sleep(0.15)
        winsound.Beep(1500, 400)
        time.sleep(0.15)
    print("  Done.")
    input("\n  Press Enter to go back...")


# --- Alert ---

def alert_user(url: str, reason: str):
    name = get_short_name(url)
    print(f"\n")
    print(f"  ╔═══════════════════════════════════════════════════════╗")
    print(f"  ║   *** IN STOCK! ***                                   ║")
    print(f"  ║   {name:<51} ║")
    print(f"  ║   {reason:<51} ║")
    print(f"  ╚═══════════════════════════════════════════════════════╝")
    print()

    if notification:
        try:
            notification.notify(
                title=f"IN STOCK! - {name}",
                message=f"{reason}\nGO GO GO!",
                timeout=30,
            )
        except Exception:
            pass

    # Aggressive alert - loud and long
    for _ in range(15):
        winsound.Beep(1000, 300)
        time.sleep(0.1)
        winsound.Beep(1500, 300)
        time.sleep(0.1)


# --- Monitoring Engine ---

def check_single_url(url: str, session: requests.Session) -> tuple[str, bool, str]:
    """Check a single URL. Returns (url, in_stock, reason)."""
    in_stock, reason, conclusive = check_stock_fast(url, session)
    if conclusive:
        return url, in_stock, f"[FAST] {reason}"
    # If fast check was inconclusive, we'll note it for browser fallback
    return url, False, f"[FAST] {reason}"


def start_monitoring(config: dict):
    urls = list(config["urls"])
    interval = config["interval_seconds"]

    if not urls:
        print("\n  No URLs to monitor! Add some products first.")
        input("\n  Press Enter to go back...")
        return

    clear_screen()
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║       MONITORING - Press Ctrl+C to stop               ║")
    print("  ╠═══════════════════════════════════════════════════════╣")
    print(f"  ║   {len(urls)} product(s) | every {interval}s | fast HTTP + browser{' ' * (11 - len(str(len(urls))) - len(str(interval)))}║")
    for i, url in enumerate(urls):
        name = get_short_name(url)
        print(f"  ║   {i+1}. {name:<49} ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()

    log(f"--- Started: {len(urls)} URLs, interval {interval}s ---")

    monitor = StatusMonitor(num_urls=len(urls))
    session = requests.Session()
    session.headers.update(HEADERS)

    # Browser setup for fallback
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(user_agent=HEADERS["User-Agent"])

    # Block unnecessary resources for speed
    def block_resources(route):
        url_lower = route.request.url.lower()
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            route.abort()
        elif any(pattern in url_lower for pattern in BLOCKED_URL_PATTERNS):
            route.abort()
        else:
            route.fallback()

    page = context.new_page()
    page.route("**/*", block_resources)

    inconclusive_count = {}  # Track how often fast check fails per URL
    browser_check_threshold = 3  # Use browser after N inconclusive fast checks

    try:
        while True:
            monitor.set_checking("Checking all URLs...")

            # PARALLEL fast HTTP checks for all URLs
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as executor:
                futures = {
                    executor.submit(check_single_url, url, session): url
                    for url in list(urls)
                }

                for future in concurrent.futures.as_completed(futures):
                    url, in_stock, reason = future.result()
                    name = get_short_name(url)

                    if in_stock:
                        monitor.stop()
                        monitor.clear_line()
                        alert_user(url, reason)
                        log(f"*** IN STOCK: {name} - {reason} ***")
                        print("  Opening in your browser...")
                        import webbrowser
                        webbrowser.open(url)
                        urls.remove(url)
                        if not urls:
                            print("\n  All items found! Done.")
                            log("--- All items found. ---")
                            browser.close()
                            pw.stop()
                            input("\n  Press Enter to go back...")
                            return
                        monitor = StatusMonitor(num_urls=len(urls))
                    else:
                        log(f"[{name}] {reason}")
                        monitor.set_result(url, reason)

                        # Track inconclusive results for browser fallback
                        if "Inconclusive" in reason:
                            inconclusive_count[url] = inconclusive_count.get(url, 0) + 1

            # Browser fallback for persistently inconclusive URLs
            for url in list(urls):
                if inconclusive_count.get(url, 0) >= browser_check_threshold:
                    monitor.set_checking(f"Browser check: {get_short_name(url)[:20]}")
                    in_stock, reason = check_stock_browser(page, url)
                    name = get_short_name(url)
                    reason_full = f"[BROWSER] {reason}"

                    log(f"[{name}] {reason_full}")

                    if in_stock:
                        monitor.stop()
                        monitor.clear_line()
                        alert_user(url, reason_full)
                        log(f"*** IN STOCK: {name} - {reason_full} ***")
                        print("  Opening in your browser...")
                        import webbrowser
                        webbrowser.open(url)
                        urls.remove(url)
                        if not urls:
                            print("\n  All items found! Done.")
                            log("--- All items found. ---")
                            browser.close()
                            pw.stop()
                            input("\n  Press Enter to go back...")
                            return
                        monitor = StatusMonitor(num_urls=len(urls))
                    else:
                        monitor.set_result(url, reason_full)

                    inconclusive_count[url] = 0  # Reset counter

            monitor.set_waiting(interval)
            time.sleep(interval)

    except KeyboardInterrupt:
        monitor.stop()
        monitor.clear_line()
        uptime = monitor._get_uptime()
        print(f"\n\n  Stopped. Ran for {uptime}, completed {monitor.total_checks} checks.")
        log(f"--- Stopped by user. {monitor.total_checks} checks. ---")
    finally:
        browser.close()
        pw.stop()

    input("\n  Press Enter to go back to menu...")


# --- Main ---

def main():
    setup_logging()
    config = load_config()

    while True:
        show_menu(config)
        choice = input("  Enter option (1-8): ").strip()

        if choice == "1":
            menu_add_url(config)
        elif choice == "2":
            menu_remove_url(config)
        elif choice == "3":
            menu_change_interval(config)
        elif choice == "4":
            start_monitoring(config)
            config = load_config()
        elif choice == "5":
            menu_view_log()
        elif choice == "6":
            menu_clear_log()
        elif choice == "7":
            menu_test_alert()
        elif choice == "8":
            print("\n  Goodbye!")
            sys.exit(0)
        else:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n\nERROR: {e}")
        print(f"\nFull error details:")
        import traceback
        traceback.print_exc()
        print("\n\nPress Enter to close...")
        input()
