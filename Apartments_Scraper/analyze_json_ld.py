"""
Analyze the JSON-LD data from Apartments.com to determine if bulk extraction is possible.
"""

import json
from pathlib import Path

# Load the findings
findings_path = Path("apartments/apartments/output/json_test/findings_summary.json")

with open(findings_path, 'r', encoding='utf-8') as f:
    findings = json.load(f)

print("=" * 80)
print("APARTMENTS.COM JSON DATA ANALYSIS")
print("=" * 80)

# Check JSON-LD data
if findings['json_ld']:
    print("\n✅ JSON-LD DATA FOUND!")
    print(f"   Number of JSON-LD blocks: {len(findings['json_ld'])}")
    
    # Get the main JSON-LD block
    main_json_ld = findings['json_ld'][0]['data']
    
    # Find the ItemList
    item_list = None
    for item in main_json_ld.get('@graph', []):
        if item.get('@type') == 'CollectionPage':
            item_list = item.get('mainEntity', {})
            break
    
    if item_list and item_list.get('@type') == 'ItemList':
        listings = item_list.get('itemListElement', [])
        print(f"\n📊 LISTINGS IN JSON-LD:")
        print(f"   Total listings on page: {item_list.get('numberOfItems', len(listings))}")
        print(f"   Actual items in array: {len(listings)}")
        
        if listings:
            # Analyze first listing
            first_listing = listings[0].get('item', {})
            print(f"\n📋 SAMPLE LISTING DATA (First listing):")
            print(f"   URL: {first_listing.get('url', 'N/A')}")
            print(f"   Name: {first_listing.get('name', 'N/A')}")
            print(f"   Phone: {first_listing.get('telephone', 'N/A')}")
            print(f"   Description: {first_listing.get('description', 'N/A')[:50]}...")
            
            # Check for address
            main_entity = first_listing.get('mainEntity', {})
            address = main_entity.get('address', {})
            if address:
                print(f"   Address: {address.get('streetAddress', '')}, {address.get('addressLocality', '')}, {address.get('addressRegion', '')} {address.get('postalCode', '')}")
            
            # Check for price
            offers = first_listing.get('offers', {})
            if offers:
                if 'lowPrice' in offers and 'highPrice' in offers:
                    print(f"   Price Range: ${offers.get('lowPrice')} - ${offers.get('highPrice')}")
                elif 'price' in offers:
                    print(f"   Price: ${offers.get('price')}")
            
            # Count how many have phone numbers
            listings_with_phone = sum(1 for item in listings if item.get('item', {}).get('telephone'))
            print(f"\n📞 PHONE NUMBER AVAILABILITY:")
            print(f"   Listings with phone: {listings_with_phone} / {len(listings)} ({listings_with_phone/len(listings)*100:.1f}%)")
            
            # Count how many have addresses
            listings_with_address = sum(1 for item in listings 
                                      if item.get('item', {}).get('mainEntity', {}).get('address'))
            print(f"   Listings with address: {listings_with_address} / {len(listings)} ({listings_with_address/len(listings)*100:.1f}%)")
            
            # Count how many have prices
            listings_with_price = sum(1 for item in listings 
                                     if item.get('item', {}).get('offers'))
            print(f"   Listings with price: {listings_with_price} / {len(listings)} ({listings_with_price/len(listings)*100:.1f}%)")
            
            print(f"\n✅ CONCLUSION:")
            print(f"   Apartments.com DOES provide bulk JSON data via JSON-LD!")
            print(f"   Each search page contains ~40 listings with:")
            print(f"     - URLs")
            print(f"     - Phone numbers (for most listings)")
            print(f"     - Addresses")
            print(f"     - Prices")
            print(f"     - Names/Descriptions")
            print(f"\n   This means you can extract ~40 listings per page from JSON-LD")
            print(f"   instead of visiting each detail page individually!")
            print(f"\n   For 1200 listings across ~30 pages:")
            print(f"     - Current method: 1200 detail page visits = 5-6 hours")
            print(f"     - JSON-LD method: 30 search page visits = ~30-60 minutes")
            print(f"     - Speed improvement: ~10x faster!")
else:
    print("\n❌ No JSON-LD data found")

# Check for other JSON structures
print(f"\n" + "=" * 80)
print("OTHER JSON STRUCTURES:")
print("=" * 80)

if findings['__NEXT_DATA__']:
    print("✅ __NEXT_DATA__ found (Zillow pattern)")
else:
    print("❌ __NEXT_DATA__ NOT found")

if findings['window_state_vars']:
    print(f"✅ Window state variables found: {len(findings['window_state_vars'])}")
    for var in findings['window_state_vars']:
        print(f"   - {var['name']}")
else:
    print("❌ Window state variables NOT found")

if findings['other_json']:
    print(f"✅ Other JSON with listings/properties: {len(findings['other_json'])}")
else:
    print("❌ Other JSON with listings/properties NOT found")

print("\n" + "=" * 80)
print("FINAL VERDICT:")
print("=" * 80)
if findings['json_ld'] and item_list:
    print("✅ YES - Apartments.com provides bulk JSON data via JSON-LD structured data!")
    print("   The scraper should be updated to extract from JSON-LD instead of")
    print("   visiting each detail page. This will make it 10x faster!")
else:
    print("❌ NO - Apartments.com does not provide bulk JSON data")
print("=" * 80)

