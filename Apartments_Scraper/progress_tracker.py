"""
Progress tracking module for scraper resume functionality.
Saves and loads scraper state to allow resuming from where it left off.
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, Optional, Tuple


class ProgressTracker:
    """Tracks scraper progress and allows resuming from saved state."""
    
    def __init__(self, city: str, output_dir: str = "output"):
        """
        Initialize progress tracker.
        
        Args:
            city: City identifier (e.g., "chicago-il")
            output_dir: Directory where progress and CSV files are stored
        """
        self.city = city
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Progress file path
        self.progress_file = os.path.join(output_dir, f"progress_{city}.json")
        
        # CSV file path
        self.csv_file = os.path.join(output_dir, f"apartments_frbo_{city}.csv")
    
    def save_progress(self, page_count: int, total_listings_found: int, 
                     last_url: str, items_scraped: int, consecutive_empty_pages: int = 0):
        """
        Save current progress to JSON file.
        
        Args:
            page_count: Current page number
            total_listings_found: Total listings discovered so far
            last_url: Last URL that was processed
            items_scraped: Total items successfully scraped and saved
            consecutive_empty_pages: Number of consecutive empty pages encountered
        """
        progress_data = {
            "city": self.city,
            "page_count": page_count,
            "total_listings_found": total_listings_found,
            "items_scraped": items_scraped,
            "last_url": last_url,
            "consecutive_empty_pages": consecutive_empty_pages,
            "last_updated": datetime.now().isoformat(),
            "csv_file": self.csv_file
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Could not save progress: {e}")
    
    def load_progress(self) -> Optional[Dict]:
        """
        Load saved progress from JSON file.
        
        Returns:
            Dictionary with progress data, or None if no progress file exists
        """
        if not os.path.exists(self.progress_file):
            return None
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Warning: Could not load progress file: {e}")
            return None
    
    def count_csv_listings(self) -> int:
        """
        Count the number of listings in the CSV file (excluding header).
        
        Returns:
            Number of listings in CSV file
        """
        if not os.path.exists(self.csv_file):
            return 0
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                # Skip header
                next(reader, None)
                # Count rows
                count = sum(1 for row in reader if row and row[0].strip())
                return count
        except Exception as e:
            print(f"⚠️ Warning: Could not count CSV listings: {e}")
            return 0
    
    def get_csv_urls(self) -> set:
        """
        Get all listing URLs from the CSV file.
        
        Returns:
            Set of listing URLs already scraped
        """
        urls = set()
        if not os.path.exists(self.csv_file):
            return urls
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('listing_url', '').strip()
                    if url:
                        urls.add(url)
        except Exception as e:
            print(f"⚠️ Warning: Could not read CSV URLs: {e}")
        
        return urls
    
    def get_resume_info(self) -> Tuple[Optional[Dict], int, set]:
        """
        Get comprehensive resume information.
        
        Returns:
            Tuple of (progress_data, csv_count, csv_urls)
            - progress_data: Saved progress dict or None
            - csv_count: Number of listings in CSV
            - csv_urls: Set of URLs already in CSV
        """
        progress_data = self.load_progress()
        csv_count = self.count_csv_listings()
        csv_urls = self.get_csv_urls()
        
        return progress_data, csv_count, csv_urls
    
    def clear_progress(self):
        """Clear/delete the progress file."""
        if os.path.exists(self.progress_file):
            try:
                os.remove(self.progress_file)
                print(f"✅ Cleared progress file: {self.progress_file}")
            except Exception as e:
                print(f"⚠️ Warning: Could not clear progress file: {e}")
    
    def get_resume_page(self) -> Optional[int]:
        """
        Determine which page to resume from.
        
        Returns:
            Page number to resume from, or None if starting fresh
        """
        progress_data = self.load_progress()
        if not progress_data:
            return None
        
        # Resume from the last page that had listings
        # If we had empty pages, we might want to go back a bit
        page_count = progress_data.get('page_count', 0)
        consecutive_empty = progress_data.get('consecutive_empty_pages', 0)
        
        # If we had empty pages, resume from a few pages back to be safe
        if consecutive_empty > 0:
            resume_page = max(1, page_count - consecutive_empty)
        else:
            resume_page = page_count
        
        return resume_page

