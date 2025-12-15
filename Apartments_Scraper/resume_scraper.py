"""
Resume script for apartments_frbo scraper.
Analyzes CSV and progress files to determine where to resume scraping.
"""

import os
import sys
import argparse
from progress_tracker import ProgressTracker


def analyze_progress(city: str = "chicago-il", output_dir: str = "output", csv_path: str = None):
    """
    Analyze current progress and provide resume information.
    
    Args:
        city: City identifier (e.g., "chicago-il")
        output_dir: Directory where progress and CSV files are stored
        csv_path: Optional custom path to CSV file (overrides default location)
    """
    tracker = ProgressTracker(city, output_dir)
    
    # If custom CSV path provided, update tracker's CSV file path
    if csv_path and os.path.exists(csv_path):
        tracker.csv_file = csv_path
    
    print("=" * 70)
    print("📊 SCRAPER PROGRESS ANALYSIS")
    print("=" * 70)
    print()
    
    # Get resume information
    progress_data, csv_count, csv_urls = tracker.get_resume_info()
    
    # CSV Analysis
    print("📄 CSV FILE ANALYSIS")
    print("-" * 70)
    csv_file = tracker.csv_file
    if os.path.exists(csv_file):
        file_size = os.path.getsize(csv_file) / (1024 * 1024)  # MB
        print(f"✅ CSV file exists: {csv_file}")
        print(f"   File size: {file_size:.2f} MB")
        print(f"   Listings in CSV: {csv_count}")
        print(f"   Unique URLs: {len(csv_urls)}")
    else:
        print(f"❌ CSV file not found: {csv_file}")
        print("   This appears to be a fresh start.")
    print()
    
    # Progress File Analysis
    print("💾 PROGRESS FILE ANALYSIS")
    print("-" * 70)
    if progress_data:
        print(f"✅ Progress file exists: {tracker.progress_file}")
        print(f"   Last updated: {progress_data.get('last_updated', 'Unknown')}")
        print(f"   Last page processed: {progress_data.get('page_count', 0)}")
        print(f"   Total listings found: {progress_data.get('total_listings_found', 0)}")
        print(f"   Items scraped: {progress_data.get('items_scraped', 0)}")
        print(f"   Consecutive empty pages: {progress_data.get('consecutive_empty_pages', 0)}")
        print(f"   Last URL: {progress_data.get('last_url', 'Unknown')}")
        
        # Calculate resume page
        resume_page = tracker.get_resume_page()
        print()
        print(f"🔄 RECOMMENDED RESUME PAGE: {resume_page}")
    else:
        print(f"❌ Progress file not found: {tracker.progress_file}")
        print("   This appears to be a fresh start.")
        resume_page = None
    print()
    
    # Comparison and Recommendations
    print("🔍 COMPARISON & RECOMMENDATIONS")
    print("-" * 70)
    
    if progress_data and csv_count > 0:
        items_scraped = progress_data.get('items_scraped', 0)
        total_found = progress_data.get('total_listings_found', 0)
        
        print(f"   Progress file says: {items_scraped} items scraped")
        print(f"   CSV file contains: {csv_count} listings")
        
        if csv_count < items_scraped:
            diff = items_scraped - csv_count
            print(f"   ⚠️  WARNING: Progress file shows {diff} more items than CSV!")
            print(f"      This might indicate some items weren't saved properly.")
        elif csv_count > items_scraped:
            diff = csv_count - items_scraped
            print(f"   ℹ️  CSV has {diff} more listings than progress file.")
            print(f"      This is normal if scraper was run multiple times.")
        else:
            print(f"   ✅ Counts match!")
        
        print()
        print("💡 RECOMMENDATION:")
        if resume_page:
            print(f"   Resume from page {resume_page} to avoid missing any listings.")
            print(f"   The scraper will automatically skip duplicates from CSV.")
        else:
            print(f"   Start from page 1 (fresh start).")
    elif csv_count > 0 and not progress_data:
        print(f"   ✅ CSV file exists with {csv_count} listings, but no progress file.")
        print(f"   The scraper will start from page 1 and skip duplicates.")
    else:
        print(f"   ✅ Fresh start - no existing data found.")
        print(f"   The scraper will start from page 1.")
    
    print()
    print("=" * 70)
    
    return resume_page, csv_count, csv_urls


def main():
    """Main entry point for resume script."""
    parser = argparse.ArgumentParser(
        description="Analyze scraper progress and determine resume point"
    )
    parser.add_argument(
        "--city",
        type=str,
        default="chicago-il",
        help="City identifier (e.g., 'chicago-il')"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for CSV and progress files"
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=None,
        help="Custom path to CSV file (if different from default location)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear progress file (start fresh)"
    )
    
    args = parser.parse_args()
    
    tracker = ProgressTracker(args.city, args.output_dir)
    
    if args.clear:
        print("🗑️  Clearing progress file...")
        tracker.clear_progress()
        print("✅ Progress file cleared. Next run will start fresh.")
        return
    
    # Analyze progress
    resume_page, csv_count, csv_urls = analyze_progress(args.city, args.output_dir, args.csv_path)
    
    # Print command to resume
    if resume_page:
        print()
        print("🚀 TO RESUME SCRAPING:")
        print("-" * 70)
        print(f"   scrapy crawl apartments_frbo -a city=\"{args.city}\" -a resume=true")
        print()
        print("   The scraper will automatically:")
        print(f"   - Load progress from page {resume_page}")
        print(f"   - Skip {csv_count} listings already in CSV")
        print(f"   - Continue until reaching 1000+ listings")
    else:
        print()
        print("🚀 TO START SCRAPING:")
        print("-" * 70)
        print(f"   scrapy crawl apartments_frbo -a city=\"{args.city}\"")
        print()
        print("   The scraper will start from page 1.")


if __name__ == "__main__":
    main()

