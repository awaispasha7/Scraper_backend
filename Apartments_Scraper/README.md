# Apartments.com FRBO Scraper

A Scrapy-based web scraper for extracting "For Rent By Owner" (FRBO) listings from apartments.com. This scraper uses Zyte API to bypass bot detection and extract comprehensive listing data including contact information.

## Features

- Scrapes all FRBO listings from apartments.com for specified cities
- Extracts 16 data fields per listing:
  - Listing URL, Title, Price
  - Beds, Baths, Square Feet
  - Owner Name, Email, Phone Numbers
  - Full Address (Street, City, State, Zip Code)
  - Neighborhood, Description
- Handles pagination automatically
- Robust error handling and retry logic
- Outputs data to CSV format
- Configurable city parameter

## Prerequisites

- Python 3.8 or higher
- Zyte API account and API key ([Sign up here](https://www.zyte.com/))

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your Zyte API key using one of these methods:

   **Option 1: Environment Variable (Recommended)**
   ```powershell
   # Windows PowerShell
   $env:ZYTE_API_KEY="your_api_key_here"
   ```

   **Option 2: Create .env file**
   ```bash
   # Copy the example file
   cp .env.example apartments_scraper/.env
   
   # Edit apartments_scraper/.env and add your key:
   ZYTE_API_KEY=your_api_key_here
   ```

   **Option 3: Settings file**
   Add to `apartments_scraper/settings.py`:
   ```python
   ZYTE_API_KEY = "your_api_key_here"
   ```

## Usage

### Basic Usage (Chicago, default)

```bash
scrapy crawl apartments_frbo -L INFO
```

### Custom City

```bash
scrapy crawl apartments_frbo -a city="new-york-ny" -L INFO
```

City format should be: `city-state` (e.g., `chicago-il`, `new-york-ny`, `los-angeles-ca`)

### Logging Levels

- `-L INFO` - Standard information (recommended)
- `-L DEBUG` - Detailed debugging information
- `-L WARNING` - Only warnings and errors
- `-L ERROR` - Only errors

## Output

Scraped data is saved to:
- `output/apartments_frbo_{city}.csv` - CSV file with all listing data

The CSV file includes all 16 fields and is encoded as UTF-8 with BOM for Excel compatibility.

## Configuration

### Spider Settings

The spider uses optimized settings for speed:
- Concurrent requests: 10
- Download delay: 0.3 seconds
- AutoThrottle: Disabled (for faster scraping)
- Retry codes: 412, 404, 429, 520, 500, 502, 503, 504, 522, 524

### Debug Mode

To save debug HTML files for troubleshooting:
```bash
scrapy crawl apartments_frbo -s DEBUG_SAVE_HTML=True -L INFO
```

This will save:
- `output/debug_search_page.html` - First search results page
- `output/debug_detail_page.html` - First listing detail page

## Project Structure

```
apartments/
├── apartments_scraper/
│   ├── spiders/
│   │   ├── apartments_frbo.py      # Main FRBO scraper
│   │   └── apartments_scraper.py   # Alternative scraper (legacy)
│   ├── middlewares.py              # Zyte API middleware
│   ├── items.py                    # Data item definitions
│   ├── pipelines.py                # Data processing pipelines
│   └── settings.py                 # Scrapy settings
├── input/
│   └── location.csv                # City locations (for apartments_scraper.py)
├── output/                         # Scraped data output directory
├── requirements.txt                # Python dependencies
├── scrapy.cfg                      # Scrapy configuration
└── README.md                       # This file
```

## Troubleshooting

### "ZYTE_API_KEY not found" Error

Make sure your API key is set using one of the methods described in Installation. The scraper will check:
1. Settings file (`apartments_scraper/settings.py`)
2. Environment variable (`ZYTE_API_KEY`)
3. `.env` file (`apartments_scraper/.env`)

### Zyte API Errors (520, 522, 524)

These are transient errors that the scraper automatically retries. If you see many of these:
- Check your Zyte API quota/credits
- Verify your API key is valid
- Wait a few minutes and try again

### No Listings Found

If the scraper finds 0 listings:
1. Check the debug HTML files (if enabled)
2. Verify the city parameter format is correct
3. Check if apartments.com has listings for that city
4. Verify the website structure hasn't changed

### CSV File Issues

If the CSV file appears corrupted:
- The scraper automatically sanitizes text to prevent corruption
- Ensure you're using UTF-8 compatible software to view the file
- Try opening in Excel or a text editor that supports UTF-8

## Notes

- The scraper respects rate limits and includes retry logic for transient errors
- Data is sanitized to prevent CSV/JSON corruption from special characters
- The scraper will continue even if some individual requests fail
- Progress is logged every 10 items scraped

## License

This project is for educational and research purposes. Please respect apartments.com's Terms of Service and robots.txt when using this scraper.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the debug HTML files if enabled
3. Check Scrapy and Zyte API documentation



