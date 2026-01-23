# Target Stock Checker

Monitors Target.com product pages and alerts you the moment an item comes in stock. Optimized for speed with parallel HTTP checks and browser fallback.

## Features

- **Fast HTTP checking** — lightweight requests that skip full page rendering
- **Browser fallback** — Playwright-based headless Chrome for JS-rendered pages
- **Parallel monitoring** — checks all URLs simultaneously
- **Resource blocking** — skips images, CSS, fonts, and analytics for faster browser loads
- **Adjustable intervals** — check as frequently as every 1 second
- **Desktop notifications** — Windows toast notifications when items are in stock
- **Sound alerts** — loud alternating beep pattern to get your attention
- **Auto-open browser** — opens the product page in your browser when found
- **Full logging** — every check is timestamped and logged to a file
- **Easy menu interface** — add/remove URLs, change interval, view logs, all from the menu

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

## Usage

```bash
python stock_checker.py
```

This opens the interactive menu:

```
  ╔═══════════════════════════════════════════════════════╗
  ║            TARGET STOCK CHECKER  v2.0                 ║
  ╠═══════════════════════════════════════════════════════╣
  ║                                                       ║
  ║   Check every: 5 second(s)                            ║
  ║   Method: Fast HTTP + Browser fallback                ║
  ║                                                       ║
  ║   Products being monitored:                           ║
  ║   1. Zephyr (A-95082138)                              ║
  ║                                                       ║
  ╠═══════════════════════════════════════════════════════╣
  ║   OPTIONS:                                            ║
  ║   1. Add a product URL                                ║
  ║   2. Remove a product                                 ║
  ║   3. Change check interval                            ║
  ║   4. START monitoring                                 ║
  ║   5. View log (last 30 entries)                       ║
  ║   6. Clear log                                        ║
  ║   7. Test alert sound                                 ║
  ║   8. Exit                                             ║
  ╚═══════════════════════════════════════════════════════╝
```

## How It Works

1. **Fast check (primary):** Makes a lightweight HTTP request to the product page and scans the raw HTML/JSON for stock indicators (`add to cart` buttons, availability status fields, out-of-stock messages).

2. **Browser check (fallback):** If the fast check can't determine stock status after 3 consecutive tries, it loads the page in a headless Chrome browser with all unnecessary resources blocked, then checks for visible "Add to Cart" buttons.

3. **Alert:** When an item is detected in stock, the script plays a loud sound, shows a desktop notification, and opens the product page in your default browser.

## Configuration

Settings are stored in `config.json` (auto-created):

```json
{
    "interval_seconds": 5,
    "urls": [
        "https://www.target.com/p/product-name/-/A-12345678"
    ]
}
```

You can edit this file directly or use the menu options.

## Files

| File | Description |
|------|-------------|
| `stock_checker.py` | Main script |
| `config.json` | URLs and interval settings |
| `stock_checker.log` | Check history log |
| `requirements.txt` | Python dependencies |

## Notes

- Very low intervals (1-2 seconds) may result in rate limiting or IP blocks from Target.
- The script only monitors and alerts — it does not automate any purchasing.
- Works best for products with a known street date or limited restocks.
