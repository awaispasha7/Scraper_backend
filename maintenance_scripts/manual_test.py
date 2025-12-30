import requests
import json

# 1. Configuration
API_KEY = "0m6jFzONhF9dPL3onXXbsQkD8wkR0Dp42hlAL1WG"
URL = "https://api.batchdata.com/api/v1/property/skip-trace"

# 2. Setup Request with SPLIT address fields
payload = {
    "requests": [
        {
            "propertyAddress": {
                "street": "5415 N Sheridan Rd",
                "city": "Chicago",
                "state": "IL",
                "zip": "60660"
            }
        }
    ]
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 3. Execution
print("--- Sending SPLIT Request for: 5415 N Sheridan Rd ---")
response = requests.post(URL, headers=headers, json=payload)

# 4. Result Analysis
if response.status_code == 200:
    data = response.json()
    # Path: results -> persons -> [0] -> meta
    person = data.get('results', {}).get('persons', [{}])[0]
    meta = person.get('meta', {})
    
    if meta.get('error'):
        print(f"❌ API Internal Error: {meta.get('errorMessage')}")
    elif not meta.get('matched'):
        print("⚠️  Warning: API call succeeded, but NO RECORD was found for this address.")
    else:
        print("✅ Success! Owner details found:")
        print(json.dumps(person, indent=2))
else:
    print(f"❌ Connection Error {response.status_code}: {response.text}")