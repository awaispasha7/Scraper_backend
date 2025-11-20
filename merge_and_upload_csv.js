/**
 * Merge two CSV files and upload to Supabase
 * 1. Read forsalebyowner_listings.csv (listings)
 * 2. Read 20251119174835_691e02f388b06_export.csv (owner data with emails/phones)
 * 3. Match by address and combine data
 * 4. Upload to Supabase listings table
 */

const fs = require('fs')
const path = require('path')

// Load environment variables from .env files
function loadEnv() {
  const envFiles = [
    path.join(__dirname, '.env'),
    path.join(__dirname, 'frontend', '.env.local'),
    path.join(__dirname, 'frontend', '.env')
  ]
  
  for (const envFile of envFiles) {
    if (fs.existsSync(envFile)) {
      const content = fs.readFileSync(envFile, 'utf-8')
      content.split('\n').forEach(line => {
        const trimmed = line.trim()
        if (trimmed && !trimmed.startsWith('#')) {
          const [key, ...valueParts] = trimmed.split('=')
          if (key && valueParts.length > 0) {
            const value = valueParts.join('=').replace(/^["']|["']$/g, '')
            process.env[key.trim()] = value.trim()
          }
        }
      })
    }
  }
}

loadEnv()

// File paths
const LISTINGS_CSV = path.join(__dirname, 'forsalebyowner_listings.csv')
const OWNER_DATA_CSV = path.join(__dirname, '20251119174835_691e02f388b06_export.csv')

// Supabase configuration
const SUPABASE_URL = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
// Use service role key for admin operations (bypasses RLS)
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set')
  console.error('   Please check your .env file in the frontend directory')
  process.exit(1)
}

// Import Supabase client
const { createClient } = require('@supabase/supabase-js')
// Use admin client with service role key to bypass RLS
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: {
    autoRefreshToken: false,
    persistSession: false
  }
})

// Normalize address for matching
function normalizeAddress(address) {
  if (!address) return ''
  return address
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/\b(north|south|east|west)\b/gi, (match) => {
      const dirs = { 'north': 'n', 'south': 's', 'east': 'e', 'west': 'w' }
      return dirs[match.toLowerCase()] || match.toLowerCase()
    })
    .replace(/\b(ave|avenue|st|street|rd|road|dr|drive|blvd|boulevard|ln|lane|pl|place|ct|court|cir|circle)\b/gi, (match) => {
      const abbrev = {
        'avenue': 'ave', 'street': 'st', 'road': 'rd', 'drive': 'dr',
        'boulevard': 'blvd', 'lane': 'ln', 'place': 'pl', 'court': 'ct', 'circle': 'cir'
      }
      return abbrev[match.toLowerCase()] || match.toLowerCase()
    })
}

// Extract street address (remove city, state, zip)
function extractStreetAddress(fullAddress) {
  if (!fullAddress) return ''
  let street = fullAddress.trim()
  // Remove "Chicago Il 60651" pattern
  street = street.replace(/\s*,\s*Chicago\s+Il\s+\d{5}.*$/i, '')
  street = street.replace(/\s+Chicago\s+Il\s+\d{5}.*$/i, '')
  street = street.replace(/\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[A-Z]{2}\s+\d{5}.*$/, '')
  return street.trim()
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
  fields.push(currentField.trim())
  return fields
}

// Extract all phones from a row
function extractPhones(row) {
  const phones = []
  for (let i = 1; i <= 7; i++) {
    const phone = row[`Mobile_${i}`]?.trim()
    if (phone && phone.length >= 10) phones.push(phone)
  }
  for (let i = 1; i <= 8; i++) {
    const phone = row[`Landline_${i}`]?.trim()
    if (phone && phone.length >= 10) phones.push(phone)
  }
  return [...new Set(phones)]
}

// Extract all emails from a row
function extractEmails(row) {
  const emails = []
  for (let i = 1; i <= 5; i++) {
    const email = row[`Email_${i}`]?.trim()
    if (email && email.includes('@')) emails.push(email)
  }
  return [...new Set(emails)]
}

// Load owner data from CSV
function loadOwnerData() {
  console.log('📖 Reading owner data CSV...')
  
  if (!fs.existsSync(OWNER_DATA_CSV)) {
    console.error(`❌ Owner data CSV not found: ${OWNER_DATA_CSV}`)
    return {}
  }
  
  const fileContent = fs.readFileSync(OWNER_DATA_CSV, 'utf-8')
  const lines = fileContent.trim().split('\n')
  
  if (lines.length < 2) {
    console.error('❌ Owner data CSV is empty')
    return {}
  }
  
  const headers = parseCSVLine(lines[0])
  const ownerDataMap = {}
  
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    
    const values = parseCSVLine(lines[i])
    if (values.length !== headers.length) {
      console.warn(`⚠️  Row ${i + 1} has ${values.length} fields, expected ${headers.length}. Skipping.`)
      continue
    }
    
    const row = {}
    headers.forEach((header, index) => {
      row[header] = values[index] || ''
    })
    
    // Get property address
    const propertyAddress = row['Property Address'] || row['INPUT_ADDRESS'] || ''
    if (!propertyAddress) continue
    
    // Normalize for matching
    const normalizedAddr = normalizeAddress(extractStreetAddress(propertyAddress))
    
    // Extract emails and phones
    const emails = extractEmails(row)
    const phones = extractPhones(row)
    
    if (emails.length > 0 || phones.length > 0) {
      ownerDataMap[normalizedAddr] = {
        emails: emails,
        phones: phones,
        propertyAddress: propertyAddress
      }
    }
  }
  
  console.log(`✅ Loaded owner data for ${Object.keys(ownerDataMap).length} addresses`)
  return ownerDataMap
}

// Load listings from CSV
function loadListings() {
  console.log('📖 Reading listings CSV...')
  
  if (!fs.existsSync(LISTINGS_CSV)) {
    console.error(`❌ Listings CSV not found: ${LISTINGS_CSV}`)
    return []
  }
  
  const fileContent = fs.readFileSync(LISTINGS_CSV, 'utf-8')
  const lines = fileContent.trim().split('\n')
  
  if (lines.length < 2) {
    console.error('❌ Listings CSV is empty')
    return []
  }
  
  const headers = parseCSVLine(lines[0])
  const listings = []
  
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    
    const values = parseCSVLine(lines[i])
    if (values.length !== headers.length) {
      console.warn(`⚠️  Row ${i + 1} has ${values.length} fields, expected ${headers.length}. Skipping.`)
      continue
    }
    
    const listing = {}
    headers.forEach((header, index) => {
      listing[header.trim()] = values[index] ? values[index].replace(/^"|"$/g, '').trim() : ''
    })
    
    listings.push(listing)
  }
  
  console.log(`✅ Loaded ${listings.length} listings`)
  return listings
}

// Merge listings with owner data
function mergeData(listings, ownerDataMap) {
  console.log('🔄 Merging listings with owner data...')
  
  const merged = listings.map(listing => {
    const address = listing['Property_Address'] || ''
    if (!address) return listing
    
    // Normalize address for matching
    const normalizedAddr = normalizeAddress(extractStreetAddress(address))
    
    // Find matching owner data
    const ownerData = ownerDataMap[normalizedAddr]
    
    if (ownerData) {
      return {
        ...listing,
        owner_emails: ownerData.emails,
        owner_phones: ownerData.phones,
        owner_email: ownerData.emails.length > 0 ? ownerData.emails[0] : null,
        owner_phone: ownerData.phones.length > 0 ? ownerData.phones[0] : null
      }
    }
    
    return listing
  })
  
  const matched = merged.filter(l => l.owner_emails || l.owner_phones).length
  console.log(`✅ Matched ${matched} out of ${merged.length} listings with owner data`)
  
  return merged
}

// Upload to Supabase
async function uploadToSupabase(listings) {
  console.log('📤 Uploading to Supabase...')
  
  const timestamp = new Date().toISOString()
  let successCount = 0
  let errorCount = 0
  
  for (let i = 0; i < listings.length; i++) {
    const listing = listings[i]
    
    try {
      // Prepare listing data
      const listingData = {
        address: listing['Property_Address'] || null,
        price: listing['Listing_Price'] || null,
        beds: listing['Number_of_Bedrooms'] || null,
        baths: listing['Number_of_Bathrooms'] || null,
        square_feet: listing['Square_Feet'] || null,
        listing_link: listing['Listing_URL'] || null,
        time_of_post: listing['Date_Posted'] || null,
        scrape_timestamp: timestamp,
        is_active: true,
        is_chicago: true,
        created_at: timestamp,
        updated_at: timestamp
      }
      
      // Add email/phone data if available
      // Store only as JSONB arrays (removed single-value columns to avoid repetition)
      if (listing.owner_emails && listing.owner_emails.length > 0) {
        listingData.owner_emails = listing.owner_emails // JSONB array
      }
      if (listing.owner_phones && listing.owner_phones.length > 0) {
        listingData.owner_phones = listing.owner_phones // JSONB array
      }
      
      // Check if listing exists
      const { data: existing } = await supabase
        .from('listings')
        .select('id')
        .eq('listing_link', listingData.listing_link)
        .maybeSingle()
      
      if (existing) {
        // Update existing
        const { error } = await supabase
          .from('listings')
          .update({
            ...listingData,
            updated_at: timestamp
          })
          .eq('id', existing.id)
        
        if (error) throw error
        successCount++
      } else {
        // Insert new
        const { error } = await supabase
          .from('listings')
          .insert(listingData)
        
        if (error) throw error
        successCount++
      }
      
      if ((i + 1) % 10 === 0) {
        console.log(`   Processed ${i + 1}/${listings.length} listings...`)
      }
    } catch (error) {
      console.error(`❌ Error uploading listing ${i + 1}:`, error.message)
      errorCount++
    }
  }
  
  console.log(`\n✅ Upload complete!`)
  console.log(`   Success: ${successCount}`)
  console.log(`   Errors: ${errorCount}`)
}

// Main function
async function main() {
  console.log('🚀 Starting CSV merge and upload process...\n')
  
  // Load data
  const ownerDataMap = loadOwnerData()
  const listings = loadListings()
  
  if (listings.length === 0) {
    console.error('❌ No listings to process')
    return
  }
  
  // Merge data
  const mergedListings = mergeData(listings, ownerDataMap)
  
  // Upload to Supabase
  await uploadToSupabase(mergedListings)
  
  console.log('\n✨ Process complete!')
}

main().catch(console.error)

