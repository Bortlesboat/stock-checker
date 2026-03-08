# Target Stock Checker v3.1

[![CI](https://github.com/Bortlesboat/stock-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/Bortlesboat/stock-checker/actions/workflows/ci.yml)

Monitors Target.com product pages and alerts you the instant an item comes in stock. Uses Playwright (headless Chromium) to render Target's React pages and detect "Add to Cart" buttons in the live DOM.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    stock_checker.py                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Menu     │───>│  Monitoring  │───>│  Alert       │   │
│  │  System   │    │  Engine      │    │  System      │   │
│  └──────────┘    └──────────────┘    └──────────────┘   │
│                         │                                │
│                         ▼                                │
│               ┌──────────────────┐                       │
│               │  Playwright       │                       │
│               │  (Headless Chrome) │                       │
│               │                    │                       │
│               │  - 1 tab per URL  │                       │
│               │  - Blocks images, │                       │
│               │    CSS, fonts,    │                       │
│               │    analytics      │                       │
│               │  - Reloads page   │                       │
│               │    each cycle     │                       │
│               │  - JS injection   │                       │
│               │    for DOM scan   │                       │
│               └──────────────────┘                       │
│                         │                                │
│                         ▼                                │
│               ┌──────────────────┐                       │
│               │  config.json      │                       │
│               │  stock_checker.log │                       │
│               └──────────────────┘                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## How Stock Detection Works

Target.com is a React single-page application. Product availability (the "Add to Cart" button) is rendered client-side by JavaScript after the initial HTML loads. This means:

1. **Raw HTTP requests don't work** — the HTML response is just a React shell with no stock info
2. **A real browser is required** — JavaScript must execute to render the product page
3. **We reload the page each check** — this forces Target's React app to re-fetch product data from their API and re-render the availability buttons

### Detection Flow (each check cycle):

```
1. page.reload() → loads fresh HTML
2. Wait for [data-test="product-price"] or [data-test="product-title"] (max 4s)
   → This confirms React has rendered the product section
3. page.evaluate(JS_CHECK_STOCK) → runs JavaScript in the page context:
   a. Check Target-specific data-test selectors for purchase buttons
   b. Check all visible buttons/links for purchase-related text
   c. Check for out-of-stock selectors (outOfStockButton, notifyMeButton)
   d. Check body text for out-of-stock phrases
   e. Check if product content exists at all (captcha/block detection)
4. Return result → alert if in stock, log either way
```

### Target-Specific Selectors Used:

**In-stock (purchase buttons):**
- `button[data-test="addToCartButton"]`
- `button[data-test="shipItButton"]`
- `button[data-test="pickItUpButton"]`
- `button[data-test="orderPickupButton"]`
- `button[data-test="deliverItButton"]`
- Any visible button with text: "add to cart", "ship it", "pick it up", "deliver it", "buy now"

**Out-of-stock indicators:**
- `[data-test="outOfStockButton"]`
- `[data-test="notifyMeButton"]`
- `[data-test="soldOutButton"]`
- Text: "out of stock", "sold out", "notify me when it's back", "currently unavailable", "temporarily out of stock"

**Product content (page loaded correctly):**
- `[data-test="product-title"]`
- `[data-test="product-price"]`
- `h1[data-test]`

### Resource Blocking (Speed Optimization):

The browser blocks these resource types to speed up page loads:
- **Types:** image, media, font, stylesheet
- **URL patterns:** analytics, tracking, ads, doubleclick, facebook, google-analytics, hotjar, optimizely, segment, newrelic, tealium, demdex, omtrdc, pinterest, twitter, snap, and all image/font file extensions

## Features

- **Interactive menu** — add/remove URLs, change interval, view logs, test alerts
- **Per-URL browser tabs** — each product gets its own pre-loaded tab
- **Configurable check interval** — 1 second minimum
- **Resource blocking** — skips images, CSS, fonts, and analytics for faster loads
- **Windows desktop notifications** — via plyer
- **Sound alerts** — alternating 1000Hz/1500Hz beeps (15 cycles)
- **Auto-opens browser** — opens the product page when stock is detected
- **Full logging** — every check logged with timestamp to stock_checker.log
- **Captcha/block detection** — detects when Target isn't serving product content
- **Live status display** — animated spinner with uptime, check count, speed (ms), and last result

## Setup

### Requirements

- Python 3.10+
- Windows (uses `winsound` for alerts)

### Install

```bash
cd stock_checker
pip install -r requirements.txt
python -m playwright install chromium
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `playwright` | Headless Chromium browser automation |
| `plyer` | Windows desktop notifications |

## Usage

```bash
python stock_checker.py
```

### Menu Options

| # | Option | Description |
|---|--------|-------------|
| 1 | Add a product URL | Paste a target.com URL (must contain A-XXXXXXXX product ID) |
| 2 | Remove a product | Remove a URL from monitoring list |
| 3 | Change check interval | Set seconds between checks (min: 1) |
| 4 | START monitoring | Begin checking all URLs |
| 5 | View log | Show last 30 log entries |
| 6 | Clear log | Delete the log file |
| 7 | Test alert sound | Play the alert beeps |
| 8 | Exit | Close the program |

### During Monitoring

The status line shows:
```
⠹ CHECKING | Up: 5m 32s | Checks: 47 | Speed: 3200ms | [Zephyr] No purchase button found
```

- **Spinner** — animated, confirms script is alive
- **Up** — total runtime
- **Checks** — total check cycles completed
- **Speed** — milliseconds for the last full check cycle
- **Last result** — what the most recent check found

Press `Ctrl+C` to stop and return to menu.

## Configuration

`config.json` (auto-created, gitignored):

```json
{
    "interval_seconds": 5,
    "urls": [
        "https://www.target.com/p/product-name/-/A-12345678"
    ]
}
```

## Files

| File | Tracked | Description |
|------|---------|-------------|
| `stock_checker.py` | Yes | Main script (v3.1) |
| `requirements.txt` | Yes | Python dependencies |
| `config.example.json` | Yes | Example config template |
| `config.json` | No (.gitignored) | User's actual URLs and settings |
| `stock_checker.log` | No (.gitignored) | Check history log |
| `.gitignore` | Yes | Excludes config, logs, pycache |

## Known Issues / Limitations

1. **Each check cycle takes ~3-5 seconds per URL** — this is the time for page reload + React render. Cannot be reduced further without losing reliability.
2. **Target may block headless browsers** — if you see "No product content (possible block/captcha)" in logs, Target is detecting the bot. The script uses a standard Chrome user-agent but doesn't have full stealth measures.
3. **Windows only** — uses `winsound.Beep()` for alerts. Would need modification for macOS/Linux.
4. **Monitoring only** — the script detects stock and alerts you. It does NOT automate any purchasing, add-to-cart, or checkout actions. You must manually complete the purchase.

## Version History

- **v1.0** — Basic requests + BeautifulSoup checker (didn't work for Target's JS-rendered pages)
- **v2.0** — Added Playwright browser, interactive menu, logging, parallel HTTP checks with browser fallback
- **v3.0** — JS fetch injection for speed (broken — Target renders buttons client-side, not in raw HTML)
- **v3.1** — Fixed: full page reload every check with DOM scan. Expanded Target selectors. Added captcha detection.
