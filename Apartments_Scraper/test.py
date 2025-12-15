"""
Test script to verify if Apartments.com provides bulk JSON data on search pages.
This script fetches a search page and analyzes all possible JSON sources.
"""

import os
import json
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ZYTE_API_KEY = os.getenv('ZYTE_API_KEY')
ZYTE_API_URL = "https://api.zyte.com/v1/extract"
TEST_URL = "https://www.apartments.com/chicago-il/for-rent-by-owner/"
OUTPUT_DIR = Path("apartments/apartments/output/json_test")

def fetch_page_with_zyte(url):
    """Fetch page using Zyte API (same as the scraper does)."""
    if not ZYTE_API_KEY:
        raise ValueError("ZYTE_API_KEY not found in environment variables")
    
    payload = {
        "url": url,
        "browserHtml": True,  # Use browser rendering
    }
    
    print(f"🔍 Fetching {url} via Zyte API...")
    resp = requests.post(
        ZYTE_API_URL,
        json=payload,
        auth=(ZYTE_API_KEY, ""),
        timeout=90,
        headers={"Content-Type": "application/json"},
    )
    
    if resp.status_code != 200:
        raise Exception(f"Zyte API returned {resp.status_code}: {resp.text[:500]}")
    
    data = resp.json()
    html = data.get("browserHtml", "")
    
    if not html:
        raise Exception("No HTML returned from Zyte API")
    
    print(f"✅ Received {len(html)} characters of HTML")
    return html

def find_json_in_scripts(html):
    """Find all script tags and extract JSON data."""
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    
    findings = {
        '__NEXT_DATA__': None,
        'window_state_vars': [],
        'json_ld': [],
        'other_json': [],
        'all_scripts_info': []
    }
    
    print(f"\n📜 Found {len(scripts)} script tags")
    
    for i, script in enumerate(scripts):
        script_text = script.string if script.string else ""
        script_type = script.get('type', '')
        script_id = script.get('id', '')
        
        if len(script_text) < 50:  # Skip tiny scripts
            continue
        
        script_info = {
            'index': i,
            'type': script_type,
            'id': script_id,
            'length': len(script_text),
            'preview': script_text[:200]
        }
        findings['all_scripts_info'].append(script_info)
        
        # Check for __NEXT_DATA__
        if script_id == '__NEXT_DATA__' or '__NEXT_DATA__' in script_text:
            try:
                json_data = json.loads(script_text)
                findings['__NEXT_DATA__'] = {
                    'found': True,
                    'keys': list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict',
                    'size': len(script_text),
                    'preview': json.dumps(json_data, indent=2)[:1000]
                }
                print(f"✅ Found __NEXT_DATA__ (Zillow pattern) - {len(script_text)} chars")
            except:
                findings['__NEXT_DATA__'] = {'found': True, 'parse_error': True}
        
        # Check for window.__*_STATE__ patterns
        window_state_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.__APOLLO_STATE__\s*=\s*({.+?});',
            r'window\.__REDUX_STATE__\s*=\s*({.+?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
        ]
        
        for pattern in window_state_patterns:
            match = re.search(pattern, script_text, re.DOTALL)
            if match:
                state_name = pattern.split('__')[1].split('_')[0]
                try:
                    json_data = json.loads(match.group(1))
                    findings['window_state_vars'].append({
                        'name': f'window.__{state_name}_STATE__',
                        'keys': list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict',
                        'size': len(match.group(1)),
                        'preview': json.dumps(json_data, indent=2)[:1000]
                    })
                    print(f"✅ Found window.__{state_name}_STATE__ - {len(match.group(1))} chars")
                except:
                    findings['window_state_vars'].append({
                        'name': f'window.__{state_name}_STATE__',
                        'parse_error': True
                    })
        
        # Check for JSON-LD
        if script_type == 'application/ld+json':
            try:
                json_data = json.loads(script_text)
                findings['json_ld'].append({
                    'type': json_data.get('@type', 'Unknown'),
                    'size': len(script_text),
                    'data': json_data
                })
                print(f"✅ Found JSON-LD: {json_data.get('@type', 'Unknown')}")
            except:
                pass
        
        # Check for listings/properties keywords in JSON-like structures
        if 'listings' in script_text.lower() or 'properties' in script_text.lower():
            # Try to find JSON objects containing these keywords
            json_patterns = [
                r'\{[^{}]*"listings"[^{}]*\}',
                r'\{[^{}]*"properties"[^{}]*\}',
                r'"listings"\s*:\s*(\[.+?\])',
                r'"properties"\s*:\s*(\[.+?\])',
            ]
            
            for pattern in json_patterns:
                matches = re.finditer(pattern, script_text, re.DOTALL)
                for match in matches:
                    try:
                        json_str = match.group(0) if match.groups() == () else match.group(1)
                        json_data = json.loads(json_str)
                        findings['other_json'].append({
                            'pattern': pattern,
                            'keys': list(json_data.keys()) if isinstance(json_data, dict) else 'Array/Other',
                            'size': len(json_str),
                            'preview': json.dumps(json_data, indent=2)[:500]
                        })
                        print(f"✅ Found JSON with listings/properties keyword")
                    except:
                        pass
    
    return findings

def search_for_listings_in_json(json_obj, path="root", max_depth=5, current_depth=0):
    """Recursively search JSON structure for listings arrays."""
    if current_depth >= max_depth:
        return []
    
    results = []
    
    if isinstance(json_obj, list):
        # Check if this looks like a listings array
        if len(json_obj) > 0:
            first_item = json_obj[0]
            if isinstance(first_item, dict):
                # Check if it has listing-like keys
                listing_keys = ['url', 'id', 'address', 'price', 'rent', 'listing', 'property', 'title', 'name']
                if any(key in str(first_item.keys()).lower() for key in listing_keys):
                    results.append({
                        'path': path,
                        'count': len(json_obj),
                        'sample_keys': list(first_item.keys())[:10] if first_item else [],
                        'sample_item': {k: v for k, v in list(first_item.items())[:5]}
                    })
        
        # Continue searching in list items
        for i, item in enumerate(json_obj[:3]):  # Only check first 3 items
            results.extend(search_for_listings_in_json(
                item, f"{path}[{i}]", max_depth, current_depth + 1
            ))
    
    elif isinstance(json_obj, dict):
        # Check for common listing-related keys
        listing_keys = ['listings', 'listResults', 'properties', 'results', 'items', 'data']
        for key in listing_keys:
            if key in json_obj:
                value = json_obj[key]
                if isinstance(value, list) and len(value) > 0:
                    results.append({
                        'path': f"{path}.{key}",
                        'count': len(value),
                        'sample_keys': list(value[0].keys())[:10] if isinstance(value[0], dict) else [],
                        'sample_item': {k: v for k, v in list(value[0].items())[:5]} if isinstance(value[0], dict) else value[0]
                    })
        
        # Continue searching in dict values
        for key, value in list(json_obj.items())[:10]:  # Only check first 10 keys
            results.extend(search_for_listings_in_json(
                value, f"{path}.{key}", max_depth, current_depth + 1
            ))
    
    return results

def deep_analyze_json(findings):
    """Deep analysis of found JSON structures to locate listings."""
    print("\n🔬 Deep analyzing JSON structures for listings...")
    
    all_listings = []
    
    # Analyze __NEXT_DATA__
    if findings['__NEXT_DATA__'] and findings['__NEXT_DATA__'].get('found'):
        print("  Analyzing __NEXT_DATA__...")
        # We'd need to parse it first - for now just note it exists
    
    # Analyze window state vars
    for state_var in findings['window_state_vars']:
        if 'preview' in state_var:
            print(f"  Analyzing {state_var['name']}...")
            try:
                # Try to parse the preview to get full structure
                # This is simplified - in real use, we'd parse the full JSON
                pass
            except:
                pass
    
    return all_listings

def save_findings(findings, html):
    """Save all findings to files for inspection."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save full HTML
    with open(OUTPUT_DIR / "full_page.html", 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n💾 Saved full HTML to {OUTPUT_DIR / 'full_page.html'}")
    
    # Save findings summary
    with open(OUTPUT_DIR / "findings_summary.json", 'w', encoding='utf-8') as f:
        # Remove previews for cleaner JSON
        clean_findings = json.loads(json.dumps(findings, default=str))
        for key in ['__NEXT_DATA__', 'window_state_vars', 'other_json']:
            if isinstance(clean_findings.get(key), list):
                for item in clean_findings[key]:
                    if 'preview' in item:
                        item['preview'] = item['preview'][:200] + "..." if len(item['preview']) > 200 else item['preview']
        json.dump(clean_findings, f, indent=2)
    print(f"💾 Saved findings summary to {OUTPUT_DIR / 'findings_summary.json'}")
    
    # Save all script tags info
    with open(OUTPUT_DIR / "all_scripts_info.txt", 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ALL SCRIPT TAGS FOUND\n")
        f.write("=" * 80 + "\n\n")
        for script_info in findings['all_scripts_info']:
            f.write(f"Script #{script_info['index']}\n")
            f.write(f"  Type: {script_info['type']}\n")
            f.write(f"  ID: {script_info['id']}\n")
            f.write(f"  Length: {script_info['length']} chars\n")
            f.write(f"  Preview: {script_info['preview']}\n")
            f.write("-" * 80 + "\n\n")
    print(f"💾 Saved script tags info to {OUTPUT_DIR / 'all_scripts_info.txt'}")

def print_summary(findings):
    """Print a summary of findings."""
    print("\n" + "=" * 80)
    print("SUMMARY OF FINDINGS")
    print("=" * 80)
    
    print(f"\n📊 Total script tags analyzed: {len(findings['all_scripts_info'])}")
    
    if findings['__NEXT_DATA__']:
        print(f"\n✅ __NEXT_DATA__ (Zillow pattern): FOUND")
        if 'keys' in findings['__NEXT_DATA__']:
            print(f"   Top-level keys: {findings['__NEXT_DATA__']['keys']}")
    else:
        print(f"\n❌ __NEXT_DATA__ (Zillow pattern): NOT FOUND")
    
    if findings['window_state_vars']:
        print(f"\n✅ Window state variables: FOUND {len(findings['window_state_vars'])}")
        for state_var in findings['window_state_vars']:
            print(f"   - {state_var['name']}")
            if 'keys' in state_var:
                print(f"     Keys: {state_var['keys'][:10]}")
    else:
        print(f"\n❌ Window state variables: NOT FOUND")
    
    if findings['json_ld']:
        print(f"\n✅ JSON-LD data: FOUND {len(findings['json_ld'])}")
        for ld in findings['json_ld']:
            print(f"   - Type: {ld['type']}")
    else:
        print(f"\n❌ JSON-LD data: NOT FOUND")
    
    if findings['other_json']:
        print(f"\n✅ Other JSON with listings/properties: FOUND {len(findings['other_json'])}")
        for json_data in findings['other_json']:
            print(f"   - Pattern: {json_data['pattern']}")
            print(f"     Keys: {json_data.get('keys', 'N/A')}")
    else:
        print(f"\n❌ Other JSON with listings/properties: NOT FOUND")
    
    print("\n" + "=" * 80)
    print("CONCLUSION:")
    if findings['__NEXT_DATA__'] or findings['window_state_vars'] or findings['other_json']:
        print("✅ Apartments.com DOES expose JSON data - check the saved files for details!")
        print("   You may be able to extract bulk listings from JSON instead of visiting each page.")
    else:
        print("❌ Apartments.com does NOT appear to expose bulk JSON data like Zillow.")
        print("   You'll need to visit each detail page individually (which is why it's slow).")
    print("=" * 80)

def main():
    """Main test function."""
    print("=" * 80)
    print("APARTMENTS.COM JSON DATA TEST")
    print("=" * 80)
    print(f"\nTesting URL: {TEST_URL}")
    print(f"Output directory: {OUTPUT_DIR}\n")
    
    try:
        # Fetch the page
        html = fetch_page_with_zyte(TEST_URL)
        
        # Find JSON in scripts
        findings = find_json_in_scripts(html)
        
        # Deep analysis
        listings = deep_analyze_json(findings)
        
        # Save findings
        save_findings(findings, html)
        
        # Print summary
        print_summary(findings)
        
        print(f"\n✅ Test complete! Check {OUTPUT_DIR} for detailed results.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()