/**
 * Script to fetch mailing addresses from ATTOM API and update Supabase database
 * This will populate mailing_address column for all listings
 */

const { createClient } = require('@supabase/supabase-js')
const fetch = require('node-fetch')
const path = require('path')
const fs = require('fs')

// Try to load .env.local from multiple locations
const envPaths = [
  path.join(__dirname, '.env.local'),
  path.join(__dirname, 'frontend', '.env.local'),
  path.join(__dirname, '.env'),
  path.join(__dirname, 'frontend', '.env')
]

for (const envPath of envPaths) {
  if (fs.existsSync(envPath)) {
    require('dotenv').config({ path: envPath })
    console.log(`📁 Loaded environment from: ${envPath}`)
    break
  }
}

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error('❌ Missing Supabase credentials in .env.local')
  console.error('   Required: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

const ATOM_API_KEY = process.env.ATTOM_API_KEY || 'ad54cb9d2627beaab4c34edb8fa8464e'
const ATOM_API_BASE_URL = 'https://api.gateway.attomdata.com/propertyapi/v1.0.0'

// Helper function to extract mailing address from ATTOM API response
function extractMailingAddress(property) {
  if (!property) return null
  
  const paths = [
    property?.assessment?.owner?.mailingAddressOneLine,
    property?.assessment?.owner?.mailingAddress?.oneLine,
    property?.assessment?.owner?.mailingAddress?.line1 && property?.assessment?.owner?.mailingAddress?.line2
      ? `${property.assessment.owner.mailingAddress.line1}, ${property.assessment.owner.mailingAddress.line2}`.trim()
      : null,
    property?.owner?.mailingAddressOneLine,
    property?.owner?.mailingAddress?.oneLine,
    property?.owner?.mailingAddress?.line1 && property?.owner?.mailingAddress?.line2
      ? `${property.owner.mailingAddress.line1}, ${property.owner.mailingAddress.line2}`.trim()
      : null,
    property?.mailingAddressOneLine,
    property?.mailingAddress?.oneLine,
  ]
  
  for (const addr of paths) {
    if (addr && typeof addr === 'string' && addr.trim() && 
        addr !== 'null' && addr !== 'None' && 
        !addr.includes('NOT AVAILABLE') && 
        !addr.includes('AVAILABLE FROM DATA SOURCE')) {
      return addr.trim()
    }
  }
  return null
}

// Parse address for ATTOM API
function parseAddress(address) {
  if (!address) return { address1: '', address2: '' }
  
  address = address.trim().replace(/\s+/g, ' ')
  
  // Normalize ordinal numbers
  address = address.replace(/(\d+)(St|Nd|Rd|Th)\b/gi, (match, num, suffix) => {
    return num + suffix.toLowerCase()
  })
  
  // Try to split into street and city/state/zip
  const parts = address.split(',').map(p => p.trim())
  
  if (parts.length >= 2) {
    return {
      address1: parts[0],
      address2: parts.slice(1).join(', ')
    }
  }
  
  // No comma: try to extract city/state/zip from end
  const cityStateZipMatch = address.match(/(Chicago|Norridge|Park Ridge|Alsip|Riverdale|Rosemont|Merrionette Park|Harwood Heights)\s+(Il|IL)\s+(\d{5})$/i)
  
  if (cityStateZipMatch) {
    const cityStateZip = cityStateZipMatch[0]
    const street = address.replace(cityStateZip, '').trim()
    return {
      address1: street,
      address2: cityStateZip
    }
  }
  
  // Fallback: use entire address as address1
  return {
    address1: address,
    address2: 'Chicago, IL'
  }
}

// Fetch mailing address from ATTOM API
async function fetchMailingAddressFromATTOM(address) {
  try {
    const { address1, address2 } = parseAddress(address)
    
    if (!address1) {
      console.warn(`⚠️ Could not parse address: ${address}`)
      return null
    }
    
    const apiUrl = `${ATOM_API_BASE_URL}/property/expandedprofile`
    const params = new URLSearchParams({
      address1: address1,
      address2: address2 || 'Chicago, IL'
    })
    
    const response = await fetch(`${apiUrl}?${params.toString()}`, {
      headers: {
        'apikey': ATOM_API_KEY,
        'Accept': 'application/json'
      }
    })
    
    if (!response.ok) {
      console.warn(`⚠️ ATTOM API error for "${address}": ${response.status} ${response.statusText}`)
      return null
    }
    
    const data = await response.json()
    
    // Extract property from response
    let property = null
    if (data.property && Array.isArray(data.property) && data.property.length > 0) {
      property = data.property[0]
    } else if (data.property && typeof data.property === 'object') {
      property = data.property
    } else if (data.properties && Array.isArray(data.properties) && data.properties.length > 0) {
      property = data.properties[0]
    } else if (data.data && data.data.property) {
      property = Array.isArray(data.data.property) ? data.data.property[0] : data.data.property
    }
    
    if (property) {
      const mailingAddress = extractMailingAddress(property)
      return mailingAddress
    }
    
    return null
  } catch (error) {
    console.error(`❌ Error fetching mailing address for "${address}":`, error.message)
    return null
  }
}

// Main function to update mailing addresses
async function updateMailingAddresses() {
  console.log('🚀 Starting mailing address update process...\n')
  
  // Fetch all listings from Supabase where mailing_address is NULL
  console.log('📥 Fetching listings from Supabase...')
  const { data: listings, error: fetchError } = await supabase
    .from('listings')
    .select('id, address, listing_link, mailing_address')
    .eq('is_active', true)
    .eq('is_chicago', true)
    .is('mailing_address', null) // Only get listings where mailing_address is NULL
    .order('created_at', { ascending: false })
  
  if (fetchError) {
    console.error('❌ Error fetching listings:', fetchError.message)
    process.exit(1)
  }
  
  if (!listings || listings.length === 0) {
    console.log('✅ No listings found that need mailing_address update')
    process.exit(0)
  }
  
  console.log(`📋 Found ${listings.length} listings without mailing_address\n`)
  
  let successCount = 0
  let failCount = 0
  let skipCount = 0
  
  // Process each listing
  for (let i = 0; i < listings.length; i++) {
    const listing = listings[i]
    const progress = `[${i + 1}/${listings.length}]`
    
    console.log(`\n${progress} Processing: ${listing.address}`)
    
    // Skip if already has mailing_address
    if (listing.mailing_address && listing.mailing_address.trim() !== '') {
      console.log(`   ⏭️  Already has mailing_address: ${listing.mailing_address}`)
      skipCount++
      continue
    }
    
    // Fetch mailing address from ATTOM API
    const mailingAddress = await fetchMailingAddressFromATTOM(listing.address)
    
    if (mailingAddress) {
      // Update in Supabase
      const { error: updateError } = await supabase
        .from('listings')
        .update({ mailing_address: mailingAddress })
        .eq('id', listing.id)
      
      if (updateError) {
        console.error(`   ❌ Failed to update: ${updateError.message}`)
        failCount++
      } else {
        console.log(`   ✅ Updated mailing_address: ${mailingAddress}`)
        successCount++
      }
    } else {
      console.log(`   ⚠️  No mailing address found from ATTOM API`)
      failCount++
    }
    
    // Add delay to avoid rate limiting (1 second between requests)
    if (i < listings.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }
  
  // Summary
  console.log('\n' + '='.repeat(50))
  console.log('📊 Summary:')
  console.log(`   ✅ Successfully updated: ${successCount}`)
  console.log(`   ❌ Failed: ${failCount}`)
  console.log(`   ⏭️  Skipped (already had mailing_address): ${skipCount}`)
  console.log(`   📋 Total processed: ${listings.length}`)
  console.log('='.repeat(50))
}

// Run the script
updateMailingAddresses()
  .then(() => {
    console.log('\n✅ Script completed!')
    process.exit(0)
  })
  .catch((error) => {
    console.error('\n❌ Script failed:', error)
    process.exit(1)
  })


