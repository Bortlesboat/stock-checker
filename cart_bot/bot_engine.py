import os
import time
import random
import threading
import winsound
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth

from cart_bot.config import CONFIG_DIR


def play_alert():
    """Play a loud alert sound."""
    try:
        for _ in range(3):
            winsound.Beep(1000, 300)
            time.sleep(0.1)
    except Exception:
        pass


def make_driver(profile_num, proxy=None, fast_mode=False):
    profile_dir = os.path.join(CONFIG_DIR, f"Profile{profile_num}")
    os.makedirs(profile_dir, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if fast_mode:
        options.page_load_strategy = "eager"
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-notifications")
        options.add_argument("--dns-prefetch-disable")
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

    if proxy:
        parts = proxy.split(":")
        if len(parts) >= 2:
            options.add_argument(f"--proxy-server={parts[0]}:{parts[1]}")

    driver = webdriver.Chrome(options=options)

    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    return driver


def handle_captcha(driver, profile_num, status_callback=None):
    try:
        captcha_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Click and Hold')]")
        if status_callback:
            status_callback(profile_num, "CAPTCHA")
        action = ActionChains(driver)
        action.click_and_hold(captcha_button).perform()
        time.sleep(3)
        action.release(captcha_button).perform()
        time.sleep(2)
        return True
    except Exception:
        return False


def run_bot(url, profile_num, total_profiles, proxy, state, selectors,
            status_callback, attempt_callback, url_callback):
    """Core bot loop. Uses callbacks for UI updates instead of direct widget access.

    Args:
        status_callback(profile_num, status, detail="")
        attempt_callback(profile_num, count)
        url_callback(profile_num, url)
    """
    # Reuse existing logged-in browser if available
    driver = state.drivers.get(profile_num)
    if driver:
        try:
            driver.get(url)
            time.sleep(1.5)
            status_callback(profile_num, "LOADED")
        except Exception:
            driver = None

    if not driver:
        try:
            driver = make_driver(profile_num, proxy, fast_mode=True)
            state.drivers[profile_num] = driver
            driver.get(url)
            time.sleep(1.5)
            status_callback(profile_num, "LOADED")
        except Exception as e:
            status_callback(profile_num, "ERROR")
            print(f"Profile {profile_num} launch error: {e}")
            return

    handle_captcha(driver, profile_num, status_callback)
    if not state.stop_all:
        status_callback(profile_num, "LOADED")

    # Stagger profiles slightly
    time.sleep(0.05 * (profile_num - 1))

    attempt = 0
    waiting = True
    js_find = selectors.get("js_find_atc", "")
    js_click = selectors.get("js_click_atc", "")
    js_page_ok = selectors.get("js_page_ok", "")
    xpath_atc = selectors["add_to_cart_xpath"]

    while not state.stop_all:
        # Pause loop
        while state.paused and not state.stop_all:
            time.sleep(0.3)
        if state.stop_all:
            break

        attempt += 1
        if attempt % 5 == 1 or not waiting:
            attempt_callback(profile_num, attempt)

        # --- PHASE 1: WAITING ---
        if waiting:
            if attempt % 5 == 1:
                status_callback(profile_num, "WAITING", "no stock yet")

            if attempt % 20 == 0:
                handle_captcha(driver, profile_num, status_callback)

            try:
                if js_find:
                    found = driver.execute_script(js_find)
                else:
                    found = driver.find_element(By.XPATH, xpath_atc)

                if found:
                    waiting = False
                    continue
                else:
                    raise Exception("not found")

            except Exception:
                driver.execute_script("location.reload();")
                time.sleep(random.uniform(0.12, 0.25))
                continue

        # --- PHASE 2: STOCK LIVE ---
        status_callback(profile_num, "CLICKING", "GO GO GO")

        try:
            js_cart_count = selectors.get("js_cart_count", "")
            count_before = -1
            if js_cart_count:
                try:
                    count_before = driver.execute_script(js_cart_count)
                    if count_before is None:
                        count_before = -1
                except Exception:
                    count_before = -1

            # Triple-click strategy
            clicked = False
            if js_click:
                clicked = driver.execute_script(js_click)
            if not clicked:
                try:
                    btn = driver.find_element(By.XPATH, xpath_atc)
                    btn.click()
                    clicked = True
                except Exception:
                    pass
            if not clicked:
                time.sleep(0.1)
                if js_click:
                    clicked = driver.execute_script(js_click)

            if not clicked:
                waiting = True
                driver.execute_script("location.reload();")
                time.sleep(random.uniform(0.12, 0.25))
                continue

            # Post-click error check
            time.sleep(0.3)
            if js_page_ok:
                try:
                    page_ok = driver.execute_script(js_page_ok)
                    if not page_ok:
                        print(f"  Profile {profile_num}: Page error after click — OOS or error state")
                        status_callback(profile_num, "TRYING", "error/OOS")
                        waiting = True
                        driver.execute_script("location.reload();")
                        time.sleep(random.uniform(0.12, 0.25))
                        continue
                except Exception:
                    pass

            # === VERIFY ===
            status_callback(profile_num, "VERIFYING", "checking...")
            js_verify_atc = selectors.get("js_verify_atc", "")
            confirmed = False

            for check in range(8):
                time.sleep(0.3)
                if state.stop_all:
                    break
                try:
                    if js_cart_count and count_before >= 0:
                        count_after = driver.execute_script(js_cart_count)
                        if count_after is not None and count_after > count_before:
                            confirmed = True
                            print(f"  Profile {profile_num}: CONFIRMED — cart count {count_before} -> {count_after}")
                            break

                    if js_verify_atc:
                        result = driver.execute_script(js_verify_atc)
                        if result == "confirmed":
                            confirmed = True
                            print(f"  Profile {profile_num}: CONFIRMED — 'added to cart' text found")
                            break
                except Exception:
                    pass

            if not confirmed:
                time.sleep(0.5)
                try:
                    if js_cart_count and count_before >= 0:
                        count_final = driver.execute_script(js_cart_count)
                        if count_final is not None and count_final > count_before:
                            confirmed = True
                            print(f"  Profile {profile_num}: CONFIRMED (late) — cart count {count_before} -> {count_final}")
                except Exception:
                    pass

            if not confirmed:
                print(f"  Profile {profile_num}: NOT confirmed — no count change, no modal. Retrying.")
                status_callback(profile_num, "TRYING", "not added")
                driver.execute_script("location.reload();")
                time.sleep(0.3)
                waiting = False
                continue

            # === CONFIRMED IN CART ===
            status_callback(profile_num, "IN CART", "CONFIRMED")
            threading.Thread(target=play_alert, daemon=True).start()

            try:
                driver.get(selectors.get("checkout_direct", selectors["cart_url"]))
                time.sleep(1)
                status_callback(profile_num, "CHECKOUT", "complete manually")
            except Exception:
                status_callback(profile_num, "IN CART", "go checkout")

            # Surface the winning browser
            try:
                driver.execute_script(
                    f"document.title = '>>> CHECKOUT - PROFILE {profile_num} <<<';"
                )
                driver.maximize_window()
                driver.switch_to.window(driver.current_window_handle)
            except Exception:
                pass

            # Minimize other browsers
            for i in range(total_profiles):
                if i + 1 != profile_num:
                    other = state.drivers.get(i + 1)
                    if other:
                        try:
                            other.minimize_window()
                        except Exception:
                            pass

            # Stop other profiles
            state.stop_all = True
            for i in range(total_profiles):
                if i + 1 != profile_num:
                    status_callback(i + 1, "STOPPED")
            return

        except Exception:
            waiting = True
            driver.execute_script("location.reload();")
            time.sleep(random.uniform(0.12, 0.25))

    status_callback(profile_num, "STOPPED")
