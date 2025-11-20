/**
 * Parse the owner CSV file and create a JSON lookup file
 * Matches listings by address and extracts email/phone data
 */

const fs = require('fs')
const path = require('path')

const CSV_PATH = path.join(__dirname, '20251119174835_691e02f388b06_export.csv')
const OUTPUT_PATH = path.join(__dirname, 'owner_data_lookup.json')

// Normalize address for matching (remove extra spaces, convert to lowercase)
function normalizeAddress(address) {
  if (!address) return ''
  return address
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/\b(ave|avenue|st|street|rd|road|dr|drive|blvd|boulevard|ln|lane|pl|place|ct|court|cir|circle)\b/gi, (match) => {
      const abbrev = {
        'avenue': 'ave', 'street': 'st', 'road': 'rd', 'drive': 'dr',
        'boulevard': 'blvd', 'lane': 'ln', 'place': 'pl', 'court': 'ct', 'circle': 'cir'
      }
      return abbrev[match.toLowerCase()] || match.toLowerCase()
    })
}

// Extract all phone numbers from a row
function extractPhones(row) {
  const phones = []
  // Mobile columns: Mobile_1 through Mobile_7
  for (let i = 1; i <= 7; i++) {
    const phone = row[`Mobile_${i}`]?.trim()
    if (phone && phone.length >= 10) {
      phones.push(phone)
    }
  }
  // Landline columns: Landline_1 through Landline_8
  for (let i = 1; i <= 8; i++) {
    const phone = row[`Landline_${i}`]?.trim()
    if (phone && phone.length >= 10) {
      phones.push(phone)
    }
  }
  return [...new Set(phones)] // Remove duplicates
}

// Extract all emails from a row
function extractEmails(row) {
  const emails = []
  // Email columns: Email_1 through Email_5
  for (let i = 1; i <= 5; i++) {
    const email = row[`Email_${i}`]?.trim()
    if (email && email.includes('@')) {
      emails.push(email)
    }
  }
  return [...new Set(emails)] // Remove duplicates
}

// Parse CSV line
function parseCSVLine(line) {
  const fields = []
  let currentField = ''
  let inQuotes = false
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
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
  return fields
}

function parseOwnerCSV() {
  console.log('📖 Reading CSV file...')
  
  if (!fs.existsSync(CSV_PATH)) {
    console.error(`❌ CSV file not found: ${CSV_PATH}`)
    return
  }
  
  const fileContent = fs.readFileSync(CSV_PATH, 'utf-8')
  const lines = fileContent.trim().split('\n')
  
  if (lines.length < 2) {
    console.error('❌ CSV file is empty or has no data rows')
    return
  }
  
  // Parse header
  const headers = parseCSVLine(lines[0])
  console.log(`📊 Found ${headers.length} columns`)
  
  // Create lookup map: normalized address -> { emails: [], phones: [], ownerName: '' }
  const lookupMap = {}
  
  // Process each data row
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    
    const values = parseCSVLine(lines[i])
    if (values.length !== headers.length) {
      console.warn(`⚠️  Row ${i + 1} has ${values.length} fields, expected ${headers.length}. Skipping.`)
      continue
    }
    
    // Create row object
    const row = {}
    headers.forEach((header, index) => {
      row[header] = values[index] || ''
    })
    
    // Get property address (try multiple fields)
    const propertyAddress = row['Property Address'] || row['INPUT_ADDRESS'] || ''
    if (!propertyAddress) continue
    
    // Normalize address for matching
    const normalizedAddr = normalizeAddress(propertyAddress)
    
    // Extract owner name
    const ownerName = row['Full Name'] || 
                     (row['First Name'] && row['Last Name'] 
                       ? `${row['First Name']} ${row['Last Name']}`.trim() 
                       : '') || 
                     ''
    
    // Extract emails and phones
    const emails = extractEmails(row)
    const phones = extractPhones(row)
    
    // Store in lookup map (use normalized address as key)
    if (!lookupMap[normalizedAddr]) {
      lookupMap[normalizedAddr] = {
        ownerName: ownerName,
        emails: [],
        phones: [],
        propertyAddress: propertyAddress // Store original address
      }
    }
    
    // Add emails and phones (avoid duplicates)
    emails.forEach(email => {
      if (!lookupMap[normalizedAddr].emails.includes(email)) {
        lookupMap[normalizedAddr].emails.push(email)
      }
    })
    
    phones.forEach(phone => {
      if (!lookupMap[normalizedAddr].phones.includes(phone)) {
        lookupMap[normalizedAddr].phones.push(phone)
      }
    })
    
    // Update owner name if we have a better one
    if (ownerName && ownerName.length > lookupMap[normalizedAddr].ownerName.length) {
      lookupMap[normalizedAddr].ownerName = ownerName
    }
  }
  
  // Save lookup map to JSON file
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(lookupMap, null, 2), 'utf-8')
  
  console.log(`✅ Created lookup file: ${OUTPUT_PATH}`)
  console.log(`📊 Total addresses in lookup: ${Object.keys(lookupMap).length}`)
  
  // Show some stats
  let withEmails = 0
  let withPhones = 0
  let withBoth = 0
  
  Object.values(lookupMap).forEach(entry => {
    if (entry.emails.length > 0) withEmails++
    if (entry.phones.length > 0) withPhones++
    if (entry.emails.length > 0 && entry.phones.length > 0) withBoth++
  })
  
  console.log(`📧 Addresses with emails: ${withEmails}`)
  console.log(`📞 Addresses with phones: ${withPhones}`)
  console.log(`✨ Addresses with both: ${withBoth}`)
}

parseOwnerCSV()

