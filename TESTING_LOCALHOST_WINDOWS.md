# Testing on Windows Localhost - See Browser Window

## Quick Start

1. **Create `.env` file** in `Scraper_backend` folder:
   ```env
   HEADLESS_BROWSER=false
   ```

2. **Run the API server**:
   ```bash
   python api_server.py
   ```
   Or double-click `run-local-windows.bat`

3. **Test location search** - browser window will appear automatically! 🎉

## What You'll See

When testing location search (e.g., Trulia → Minneapolis):
- Chrome window opens
- Navigates to trulia.com
- Types in search box
- Clicks suggestion
- Navigates to results
- URL is captured and returned

**You can watch everything happen in real-time!**

## Troubleshooting

**Browser doesn't appear?**
- Check `.env` file has `HEADLESS_BROWSER=false`
- Make sure Chrome is installed
- Check logs for: `✓ GUI available on win32`

That's it! No xvfb needed on Windows - it just works! ✅
