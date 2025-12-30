import re

# Known platform placeholder domains and specific emails
PLACEHOLDER_DOMAINS = [
    'hotpads.com',
    'zillow.com',
    'trulia.com',
    'apartments.com',
    'redfin.com',
    'streetlines.com',
]

PLACEHOLDER_EMAILS = [
    'support@hotpads.com',  # Explicitly listed as invalid
    'noreply@zillow.com',
    'contact@trulia.com',
    'help@apartments.com',
]

# Patterns for fake or generic phone numbers
PLACEHOLDER_PHONE_PATTERNS = [
    r'000-000-0000',
    r'111-111-1111',
    r'123-456-7890',
    r'\(800\) 000-0000',
]

def is_placeholder_email(email):
    """
    Checks if an email is a platform placeholder.
    """
    if not email:
        return True
    
    email = str(email).lower().strip()
    
    if email in PLACEHOLDER_EMAILS:
        return True
        
    for domain in PLACEHOLDER_DOMAINS:
        if email.endswith(f"@{domain}"):
            return True
            
    return False

def is_placeholder_phone(phone):
    """
    Checks if a phone number is a placeholder.
    """
    if not phone:
        return True
        
    phone_clean = re.sub(r'\D', '', str(phone))
    
    # Check if it's all same digits (0000000000)
    if len(phone_clean) >= 10 and len(set(phone_clean)) == 1:
        return True
        
    # Check common fake patterns
    for pattern in PLACEHOLDER_PHONE_PATTERNS:
        if re.search(pattern, str(phone)):
            return True
            
    return False

def clean_owner_data(owner_name, email, phone):
    """
    Cleans owner data, returning None for placeholders.
    """
    clean_email = email if not is_placeholder_email(email) else None
    clean_phone = phone if not is_placeholder_phone(phone) else None
    
    # If name is just "Support" or "Admin", it's likely a placeholder
    clean_name = owner_name
    if owner_name and str(owner_name).lower().strip() in ['support', 'admin', 'hotpads support', 'listing agent', 'property manager', 'leasing office', 'null', 'none']:
        clean_name = None
        
    return clean_name, clean_email, clean_phone

def is_valid_owner_name(name):
    """Check if owner name is valid (not placeholder)."""
    if not name:
        return False
    name_lower = str(name).lower().strip()
    invalid_names = ['support', 'admin', 'hotpads support', 'listing agent', 
                     'property manager', 'leasing office', 'null', 'none', '']
    return name_lower not in invalid_names

def is_owner_data_complete(owner_name, owner_email, owner_phone, mailing_address=None):
    """
    Check if owner data is considered COMPLETE for enrichment purposes.
    Complete = all three contact fields present AND valid (not placeholders) AND mailing_address present.
    Returns: (is_complete: bool, missing_fields: dict)
    """
    clean_name, clean_email, clean_phone = clean_owner_data(owner_name, owner_email, owner_phone)
    
    # Check mailing address validity (simple check for non-empty string)
    has_mailing = mailing_address is not None and str(mailing_address).strip() != "" and str(mailing_address).lower() != "null" and str(mailing_address).lower() != "none"
    
    missing = {
        "owner_name": clean_name is None,
        "owner_email": clean_email is None,
        "owner_phone": clean_phone is None,
        "mailing_address": not has_mailing
    }
    
    # All fields must be present to be considered "complete" regarding enrichment
    # We explicitly require mailing_address now per requirements
    is_complete = all([clean_name, clean_email, clean_phone, has_mailing])
    return is_complete, missing
