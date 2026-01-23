"""
Stock Checker for Target - Optimized for maximum speed.
Parallel browser tabs with JS-injection checks. No wasted time.
"""

import json
import os
import re
import time
import sys
import winsound
import threading
import logging

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
    "google-analytics", "hotjar", "optimizely", "segment", "newrelic",
    "tealium", "demdex", "omtrdc", "pinterest", "twitter", "snap",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".webm",
]

SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# JavaScript to inject into page for DOM stock checking
JS_CHECK_STOCK = """
() => {
    // Check for add-to-cart type buttons (Target-specific data-test attributes)
    const inStockSelectors = [
        'button[data-test="addToCartButton"]',
        'button[data-test="shipItButton"]',
        'button[data-test="pickItUpButton"]',
        'button[data-test="orderPickupButton"]',
        'button[data-test="deliverItButton"]',
        '[data-test="addToCartButton"]',
        '[data-test="shipItButton"]',
        '[data-test="pickItUpButton"]',
    ];

    for (const sel of inStockSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            // Check if element is visible (not hidden)
            const style = window.getComputedStyle(el);
            if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                return { inStock: true, reason: `Button: ${el.innerText.trim().substring(0, 30)}` };
            }
        }
    }

    // Check for any visible button/link with purchase-related text
    const allClickables = document.querySelectorAll('button, a[role="button"], [role="button"]');
    for (const el of allClickables) {
        const text = el.innerText?.toLowerCase()?.trim() || '';
        if ((text.includes('add to cart') || text.includes('ship it') ||
             text.includes('pick it up') || text.includes('deliver it') ||
             text === 'buy now') && el.offsetParent !== null) {
            const style = window.getComputedStyle(el);
            if (style.display !== 'none' && style.visibility !== 'hidden') {
                return { inStock: true, reason: `Button text: "${el.innerText.trim().substring(0, 30)}"` };
            }
        }
    }

    // Check for out-of-stock indicators (Target-specific)
    const outOfStockSelectors = [
        '[data-test="outOfStockButton"]',
        '[data-test="notifyMeButton"]',
        '[data-test="soldOutButton"]',
    ];

    for (const sel of outOfStockSelectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) {
            return { inStock: false, reason: `OOS button: ${el.innerText.trim().substring(0, 30)}` };
        }
    }

    // Check body text for out-of-stock phrases
    const bodyText = document.body?.innerText?.toLowerCase() || '';
    const outPhrases = [
        'out of stock', 'sold out', "notify me when it's back",
        'currently unavailable', 'temporarily out of stock',
        'this item is not available', 'not sold at this store'
    ];
    for (const phrase of outPhrases) {
        if (bodyText.includes(phrase)) {
            return { inStock: false, reason: phrase };
        }
    }

    // Check if page has product content at all (might be error/captcha page)
    const hasProductInfo = document.querySelector('[data-test="product-title"], h1[data-test], [data-test="product-price"]');
    if (!hasProductInfo) {
        return { inStock: false, reason: 'No product content (possible block/captcha)' };
    }

    return { inStock: false, reason: 'No purchase button found' };
}
"""



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
    match = re.search(r"A-(\d+)", url)
    return match.group(1) if match else ""


# --- Monitor Display ---

class StatusMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.total_checks = 0
        self.current_activity = "Starting..."
        self.state = "idle"
        self.next_check_at = 0
        self.check_speed_ms = 0  # Last check duration
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
            status = f"{spinner} CHECKING"
        elif self.state == "waiting":
            remaining = max(0, int(self.next_check_at - time.time()))
            status = f"{spinner} Next in {remaining}s"
        else:
            status = f"{spinner} Starting"

        speed = f"{self.check_speed_ms}ms" if self.check_speed_ms else "---"

        line = (
            f"\r  {status} | "
            f"Up: {uptime} | "
            f"Checks: {self.total_checks} | "
            f"Speed: {speed} | "
            f"{self.current_activity}"
        )
        sys.stdout.write(f"{line:<140}")
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

    def set_result(self, activity: str, speed_ms: int = 0):
        with self._lock:
            self.total_checks += 1
            self.current_activity = activity
            if speed_ms:
                self.check_speed_ms = speed_ms

    def stop(self):
        self._running = False

    def clear_line(self):
        sys.stdout.write("\r" + " " * 140 + "\r")
        sys.stdout.flush()


# --- Menu ---

def show_menu(config: dict):
    clear_screen()
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║          TARGET STOCK CHECKER  v3.1 (FIXED)             ║")
    print("  ╠═══════════════════════════════════════════════════════╣")
    print("  ║                                                       ║")
    print(f"  ║   Check every: {config['interval_seconds']} second(s){' ' * (34 - len(str(config['interval_seconds'])))}║")
    print("  ║   Method: Browser reload + DOM scan (reliable)        ║")
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
    print("  1 = fastest, 3 = fast, 5 = balanced, 10 = safe")
    print()
    print("  TIP: With the new speed optimizations, each check takes")
    print("  ~200-500ms. So interval 1 = checking every ~1.5 seconds total.")

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
        time.sleep(0.1)
        winsound.Beep(1500, 400)
        time.sleep(0.1)
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

    # Aggressive alert
    for _ in range(15):
        winsound.Beep(1000, 300)
        time.sleep(0.08)
        winsound.Beep(1500, 300)
        time.sleep(0.08)


# --- Monitoring Engine ---

def check_page(page, url: str) -> tuple[bool, str]:
    """
    Reload the page and check the rendered DOM for stock buttons.
    This is the only reliable method for Target's React-rendered pages.
    """
    try:
        page.reload(wait_until="domcontentloaded", timeout=12000)
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=12000)
        except Exception as e:
            return False, f"Load error: {e}"

    # Wait for React to render product content (price or title = page is loaded)
    try:
        page.wait_for_selector('[data-test="product-price"], [data-test="product-title"], h1[data-test]', timeout=4000)
    except Exception:
        pass  # Timeout - page might be blocked or slow, we'll still check DOM

    # Check rendered DOM with JavaScript
    try:
        result = page.evaluate(JS_CHECK_STOCK)
        return result["inStock"], result["reason"]
    except Exception:
        return False, "DOM check failed"


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
    print(f"  ║   {len(urls)} product(s) | every {interval}s | full DOM check{' ' * (15 - len(str(len(urls))) - len(str(interval)))}║")
    for i, url in enumerate(urls):
        name = get_short_name(url)
        print(f"  ║   {i+1}. {name:<49} ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()
    print("  Loading pages for the first time...")

    log(f"--- Started: {len(urls)} URLs, interval {interval}s ---")

    monitor = StatusMonitor()

    # Setup browser
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT)

    # Block unnecessary resources
    def block_resources(route):
        req_url = route.request.url.lower()
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            route.abort()
        elif any(p in req_url for p in BLOCKED_URL_PATTERNS):
            route.abort()
        else:
            route.fallback()

    # Create one page per URL for parallel checking
    pages = {}
    for url in urls:
        page = context.new_page()
        page.route("**/*", block_resources)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)  # Initial render only
        except Exception as e:
            log(f"Initial load error for {get_short_name(url)}: {e}")
        pages[url] = page

    print("  Pages loaded. Monitoring started!\n")

    try:
        while True:
            monitor.set_checking("Checking...")
            start_time = time.time()

            # Check all pages (each gets a fresh reload)
            for url in list(urls):
                page = pages.get(url)
                if not page:
                    continue

                name = get_short_name(url)
                in_stock, reason = check_page(page, url)
                elapsed_ms = int((time.time() - start_time) * 1000)

                if in_stock:
                    monitor.stop()
                    monitor.clear_line()
                    alert_user(url, reason)
                    log(f"*** IN STOCK: {name} - {reason} ***")
                    print("  Opening in your browser...")
                    import webbrowser
                    webbrowser.open(url)
                    urls.remove(url)
                    page.close()
                    del pages[url]
                    if not urls:
                        print("\n  All items found! Done.")
                        log("--- All items found. ---")
                        browser.close()
                        pw.stop()
                        input("\n  Press Enter to go back...")
                        return
                    monitor = StatusMonitor()
                else:
                    log(f"[{name}] {reason}")
                    monitor.set_result(f"[{name[:15]}] {reason}", elapsed_ms)

            elapsed_ms = int((time.time() - start_time) * 1000)
            monitor.check_speed_ms = elapsed_ms
            monitor.set_waiting(interval)
            time.sleep(interval)

    except KeyboardInterrupt:
        monitor.stop()
        monitor.clear_line()
        uptime = monitor._get_uptime()
        print(f"\n\n  Stopped. Ran for {uptime}, completed {monitor.total_checks} checks.")
        log(f"--- Stopped. {monitor.total_checks} checks in {uptime}. ---")
    finally:
        for p in pages.values():
            try:
                p.close()
            except Exception:
                pass
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
