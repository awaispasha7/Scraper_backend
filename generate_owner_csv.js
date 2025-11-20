/**
 * Generate CSV with Owner Information
 * Reads forsalebyowner_listings.csv and creates a new CSV with:
 * First Name, Last Name, Address, City, State, Zip
 * 
 * Fetches owner names from the owner-info API endpoint
 */

const fs = require('fs')
const path = require('path')

// dotenv is optional - script doesn't need environment variables
// (it just calls the API endpoint which is already running)

// Node.js 18+ has built-in fetch, no need to import

// Parse address into components
function parseAddress(fullAddress) {
  if (!fullAddress) return { address: '', city: '', state: '', zip: '' }
  
  // Remove extra spaces
  fullAddress = fullAddress.trim().replace(/\s+/g, ' ')
  
  // Multi-word cities that need special handling (order matters - longest first)
  const multiWordCities = [
    'Harwood Heights',
    'Merrionette Park', 
    'Park Ridge'
  ]
  
  // Single-word cities
  const singleWordCities = ['Chicago', 'Norridge', 'Alsip', 'Riverdale', 'Rosemont']
  
  // Extract state and ZIP together - state MUST come before ZIP
  // Pattern: "IL 60634" or "Il 60634" - state abbreviation followed by space and 5-digit ZIP
  // Find the LAST occurrence (at the end of address) to get the actual ZIP code, not house numbers
  // Search from the end backwards to find the last "State ZIP" pattern
  const stateZipPattern = /\b([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b/gi
  const allMatches = []
  let match
  
  // Find all matches
  while ((match = stateZipPattern.exec(fullAddress)) !== null) {
    allMatches.push(match)
  }
  
  // Use the last match (the actual ZIP code at the end)
  const stateZipMatch = allMatches.length > 0 ? allMatches[allMatches.length - 1] : null
  
  if (!stateZipMatch) {
    // Can't parse without state and ZIP
    return { address: fullAddress, city: '', state: '', zip: '' }
  }
  
  const state = stateZipMatch[1].toUpperCase()
  const zip = stateZipMatch[2].split('-')[0] // Remove ZIP+4 extension
  
  // Find everything before "State ZIP"
  const stateZipIndex = stateZipMatch.index
  const beforeStateZip = fullAddress.substring(0, stateZipIndex).trim()
  
  // Now split address and city
  let city = ''
  let address = ''
  
  // Try multi-word cities first (check from end of string for longest match)
  for (const cityName of multiWordCities) {
    // Look for city name at the end of the string (before state)
    const cityPattern = new RegExp(`\\b${cityName.replace(/\s+/g, '\\s+')}\\s*$`, 'i')
    if (cityPattern.test(beforeStateZip)) {
      city = cityName
      address = beforeStateZip.replace(new RegExp(`\\s+${cityName.replace(/\s+/g, '\\s+')}\\s*$`, 'i'), '').trim()
      break
    }
  }
  
  // If no multi-word city found, try single-word cities
  if (!city) {
    for (const cityName of singleWordCities) {
      const cityPattern = new RegExp(`\\b${cityName}\\s*$`, 'i')
      if (cityPattern.test(beforeStateZip)) {
        city = cityName
        address = beforeStateZip.replace(new RegExp(`\\s+${cityName}\\s*$`, 'i'), '').trim()
        break
      }
    }
  }
  
  // If still no city found, assume last word before state is city
  if (!city) {
    const words = beforeStateZip.split(/\s+/)
    if (words.length >= 2) {
      city = words[words.length - 1]
      address = words.slice(0, -1).join(' ')
    } else {
      address = beforeStateZip
      city = ''
    }
  }
  
  return { address, city, state, zip }
}

// Split owner name into first and last name
function splitOwnerName(fullName) {
  if (!fullName || fullName === 'null' || fullName === 'None') {
    return { firstName: '', lastName: '' }
  }
  
  const name = fullName.trim()
  
  // Handle names with commas (e.g., "MACDONALD,DONNA" or "HARRIS,LUBERTHA TRUST")
  // Format is usually "Last, First" or "Last, First Middle" or "Last, First Suffix"
  if (name.includes(',')) {
    const commaParts = name.split(',').map(p => p.trim()).filter(p => p)
    if (commaParts.length >= 2) {
      // First part is last name
      const lastName = commaParts[0]
      // Second part is first name (may include middle name and/or suffix)
      let firstName = commaParts[1]
      let suffix = ''
      
      // Check if second part ends with a suffix
      const suffixPattern = /\s+(JR|SR|II|III|IV|V|LLC|INC|CORP|TRUST|NUMBER)$/i
      const suffixMatch = firstName.match(suffixPattern)
      if (suffixMatch) {
        suffix = suffixMatch[1]
        firstName = firstName.substring(0, suffixMatch.index).trim()
      }
      
      return { 
        firstName: firstName || '', 
        lastName: lastName + (suffix ? ' ' + suffix : '')
      }
    }
  }
  
  // Handle names with special suffixes (JR, SR, II, III, LLC, INC, CORP, TRUST, NUMBER, etc.)
  const suffixPattern = /\s+(JR|SR|II|III|IV|V|LLC|INC|CORP|TRUST|NUMBER)$/i
  const suffixMatch = name.match(suffixPattern)
  let nameWithoutSuffix = name
  let suffix = ''
  
  if (suffixMatch) {
    suffix = suffixMatch[1]
    nameWithoutSuffix = name.substring(0, suffixMatch.index).trim()
  }
  
  const parts = nameWithoutSuffix.split(/\s+/).filter(p => p)
  
  if (parts.length === 0) {
    return { firstName: '', lastName: '' }
  }
  
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: suffix || '' }
  }
  
  // Last name is the last part (plus suffix if exists)
  const lastName = parts[parts.length - 1] + (suffix ? ' ' + suffix : '')
  // First name is everything else
  const firstName = parts.slice(0, -1).join(' ')
  
  return { firstName, lastName }
}

// Fetch owner name from API
async function fetchOwnerName(address) {
  try {
    // Call the owner-info API endpoint
    // Note: Make sure Next.js server is running on localhost:3000
    const apiUrl = `http://localhost:3000/api/owner-info?address=${encodeURIComponent(address)}`
    
    const response = await fetch(apiUrl)
    if (!response.ok) {
      if (response.status === 503 || response.status === 500) {
        console.warn(`⚠️ Server error for ${address.substring(0, 30)}... - is Next.js server running?`)
      }
      return null
    }
    
    const data = await response.json()
    return data.ownerName || null
  } catch (error) {
    if (error.code === 'ECONNREFUSED') {
      console.warn(`⚠️ Cannot connect to API - is Next.js server running on localhost:3000?`)
    } else {
      console.warn(`⚠️ Error fetching owner name for ${address.substring(0, 30)}...:`, error.message)
    }
    return null
  }
}

// Main function
async function generateCSV() {
  console.log('📖 Reading forsalebyowner_listings.csv...')
  
  const csvPath = path.join(__dirname, 'forsalebyowner_listings.csv')
  const csvContent = fs.readFileSync(csvPath, 'utf-8')
  const lines = csvContent.split('\n').filter(line => line.trim())
  
  // Skip header
  const header = lines[0]
  const dataLines = lines.slice(1)
  
  console.log(`📊 Found ${dataLines.length} listings`)
  console.log('🔄 Processing listings and fetching owner names...')
  console.log('   (This may take a while as we fetch from API)')
  
  const results = []
  
  for (let i = 0; i < dataLines.length; i++) {
    const line = dataLines[i]
    if (!line.trim()) continue
    
    // Parse CSV line (handle quoted fields)
    const fields = []
    let currentField = ''
    let inQuotes = false
    
    for (let j = 0; j < line.length; j++) {
      const char = line[j]
      if (char === '"') {
        inQuotes = !inQuotes
      } else if (char === ',' && !inQuotes) {
        fields.push(currentField.trim())
        currentField = ''
      } else {
        currentField += char
      }
    }
    fields.push(currentField.trim()) // Last field
    
    const propertyAddress = fields[0] || ''
    
    if (!propertyAddress) continue
    
    // Parse address
    const addressParts = parseAddress(propertyAddress)
    
    // Fetch owner name
    console.log(`   [${i + 1}/${dataLines.length}] Fetching owner for: ${addressParts.address.substring(0, 30)}...`)
    const ownerName = await fetchOwnerName(propertyAddress)
    const { firstName, lastName } = splitOwnerName(ownerName)
    
    results.push({
      firstName,
      lastName,
      address: addressParts.address,
      city: addressParts.city,
      state: addressParts.state,
      zip: addressParts.zip
    })
    
    // Small delay to avoid overwhelming the API
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  
  // Generate new CSV
  console.log('\n📝 Generating new CSV file...')
  const outputPath = path.join(__dirname, 'owner_listings.csv')
  const csvLines = ['First Name,Last Name,Address,City,State,Zip']
  
  for (const result of results) {
    // Escape fields that contain commas or quotes
    const escapeField = (field) => {
      if (!field) return ''
      if (field.includes(',') || field.includes('"') || field.includes('\n')) {
        return `"${field.replace(/"/g, '""')}"`
      }
      return field
    }
    
    csvLines.push([
      escapeField(result.firstName),
      escapeField(result.lastName),
      escapeField(result.address),
      escapeField(result.city),
      escapeField(result.state),
      escapeField(result.zip)
    ].join(','))
  }
  
  fs.writeFileSync(outputPath, csvLines.join('\n'), 'utf-8')
  console.log(`✅ Created ${outputPath}`)
  console.log(`📊 Total records: ${results.length}`)
  console.log(`   With owner names: ${results.filter(r => r.firstName || r.lastName).length}`)
  console.log(`   Without owner names: ${results.filter(r => !r.firstName && !r.lastName).length}`)
}

// Run the script
generateCSV().catch(error => {
  console.error('❌ Error:', error)
  process.exit(1)
})


