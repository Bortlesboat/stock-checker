# Claude Code Instructions

## Project Overview

Real-time Target.com product stock monitor using Playwright headless browser. Detects "Add to Cart" buttons in Target's React-rendered DOM.

## Architecture

- `stock_checker.py` — main monitoring script (interactive menu + monitoring loop)
- `cart_bot/` — modular cart automation package (separate from stock checking)
- `config.json` — user URLs and check interval (gitignored)
- `config.example.json` — template config

## Key Dependencies

- playwright (headless Chromium browser automation)
- plyer (desktop notifications)
- winsound (Windows-only, stdlib)

## Development Notes

- Target.com is a React SPA — raw HTTP requests cannot detect stock status
- Each check cycle: page.reload() → wait for React render → JS DOM scan
- Resource blocking (images, CSS, fonts, analytics) speeds up checks
- The pre-commit hook scans for sensitive data before allowing commits

## Platform

Windows-only due to `winsound` dependency. Would need platform abstraction for cross-OS support.
