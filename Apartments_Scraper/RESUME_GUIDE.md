# Resume Mechanism Guide

This guide explains how to use the resume/rollback mechanism to continue scraping from where you left off.

## Overview

The resume mechanism consists of:
1. **Progress Tracker** (`progress_tracker.py`) - Saves/loads scraper state
2. **Resume Script** (`resume_scraper.py`) - Analyzes progress and CSV to determine resume point
3. **Spider Integration** - Automatically saves progress and can resume from saved state

## How It Works

### Progress Tracking

The scraper automatically saves progress after each page is processed. Progress is saved to:
```
output/progress_{city}.json
```

The progress file contains:
- Current page number
- Total listings found
- Items scraped
- Last URL processed
- Consecutive empty pages count
- Timestamp

### CSV Analysis

The resume script analyzes:
- **CSV file**: Counts listings already scraped
- **Progress file**: Loads saved state (page number, etc.)
- **Comparison**: Determines where to resume

## Usage

### 1. Check Current Progress

Run the resume script to see current status:

```bash
python resume_scraper.py --city chicago-il
```

If your CSV is in a different location:

```bash
python resume_scraper.py --city chicago-il --csv-path "c:\Users\Admin\Desktop\apartments_frbo_chicago-il.csv"
```

### 2. Resume Scraping

To resume from saved progress:

```bash
scrapy crawl apartments_frbo -a city="chicago-il" -a resume=true
```

Or with a custom URL:

```bash
scrapy crawl apartments_frbo -a url="https://www.apartments.com/chicago-il/for-rent-by-owner/" -a resume=true
```

### 3. Start Fresh (Ignore Progress)

To start from page 1 (but still skip duplicates from CSV):

```bash
scrapy crawl apartments_frbo -a city="chicago-il"
```

### 4. Clear Progress File

To clear the progress file and start completely fresh:

```bash
python resume_scraper.py --city chicago-il --clear
```

## Features

### Automatic Duplicate Prevention

- The scraper automatically loads URLs from CSV to skip duplicates
- Works even without resume mode
- Prevents re-scraping listings already in CSV

### Smart Resume Logic

- If progress file exists: Resumes from saved page number
- If only CSV exists: Starts from page 1 but skips duplicates
- If nothing exists: Fresh start

### Progress Saving

- Progress is saved after each page is processed
- Final progress is saved when spider closes
- Allows recovery from crashes/interruptions

## Example Workflow

1. **Start scraping:**
   ```bash
   scrapy crawl apartments_frbo -a city="chicago-il"
   ```

2. **Scraper stops at 357 listings** (interrupted or hit stopping condition)

3. **Check progress:**
   ```bash
   python resume_scraper.py --city chicago-il
   ```
   Output shows:
   - 357 listings in CSV
   - Last page processed: 18
   - Recommended resume page: 18

4. **Resume scraping:**
   ```bash
   scrapy crawl apartments_frbo -a city="chicago-il" -a resume=true
   ```
   - Starts from page 18
   - Skips 357 URLs already in CSV
   - Continues until 1000+ listings or stopping condition

## Troubleshooting

### CSV Not Found

If the resume script can't find your CSV:
- Check the file path
- Use `--csv-path` to specify custom location
- Ensure CSV is in the `output/` folder for automatic detection

### Progress File Out of Sync

If progress file shows different count than CSV:
- Progress file may be outdated
- CSV may have been manually edited
- Use `--clear` to reset progress file

### Resume Starts from Wrong Page

If resume starts from wrong page:
- Check progress file: `output/progress_{city}.json`
- Manually edit page number if needed
- Or use `--clear` to start fresh

## Files Created

- `output/progress_{city}.json` - Progress tracking file
- `output/apartments_frbo_{city}.csv` - Scraped listings (or custom path)

## Notes

- Progress is saved automatically - no manual intervention needed
- Resume mode loads CSV URLs to prevent duplicates
- Progress file is updated after each page
- Can resume multiple times without losing data

