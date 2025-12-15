import csv
from collections import Counter

csv_file = "output/apartments_frbo_chicago-il.csv"

print("🔍 Checking for duplicates in CSV file...")
print("=" * 60)

urls = []
line_numbers = {}

# Read CSV and extract URLs
with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for line_num, row in enumerate(reader, start=2):  # Start at 2 (line 1 is header)
        url = row.get('listing_url', '').strip()
        if url:
            urls.append(url)
            if url not in line_numbers:
                line_numbers[url] = []
            line_numbers[url].append(line_num)

# Count occurrences
url_counts = Counter(urls)
duplicates = {url: count for url, count in url_counts.items() if count > 1}

# Print results
total_rows = len(urls)
unique_urls = len(set(urls))
duplicate_count = len(duplicates)

print(f"📊 Total rows with URLs: {total_rows}")
print(f"✅ Unique URLs: {unique_urls}")
print(f"🔄 Duplicate URLs found: {duplicate_count}")

if duplicates:
    print("\n" + "=" * 60)
    print("⚠️  DUPLICATE ENTRIES FOUND:")
    print("=" * 60)
    for url, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
        print(f"\n🔗 URL appears {count} times:")
        print(f"   {url}")
        print(f"   Found on lines: {', '.join(map(str, line_numbers[url]))}")
else:
    print("\n" + "=" * 60)
    print("✅ NO DUPLICATES FOUND!")
    print("=" * 60)
    print("All URLs are unique.")

print("\n" + "=" * 60)


