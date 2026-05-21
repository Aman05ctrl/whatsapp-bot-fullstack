"""
Property Handler - Smart Property Search
=========================================
Filters and matches properties based on user criteria.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def find_best_property(
    properties: List[Dict],
    prop_type: Optional[str] = None,
    city: Optional[str] = None,
    budget: Optional[int] = None,
    margin: int = 30000
) -> Optional[Dict]:
    """
    Find the BEST matching property for user.
    
    Priority:
    1. Exact type + city + within budget margin
    2. Type + city match (any price)
    3. Type match only
    4. None if nothing matches
    
    Args:
        properties: List of available properties
        prop_type: Desired type (Apartment, Villa, etc.)
        city: Desired city
        budget: User's budget in AED
        margin: Budget flexibility (default ±30,000 AED)
    
    Returns:
        Best matching property dict or None
    """
    if not properties:
        return None
    
    prop_type_lower = (prop_type or "").lower()
    city_lower = (city or "").lower()
    
    # Filter out sold properties
    available = [p for p in properties if not p.get('is_sold', False)]
    
    if not available:
        return None
    
    # Priority 1: Type + City + Budget match
    if prop_type and city and budget:
        budget_min = budget - margin
        budget_max = budget + margin
        
        matches = []
        for p in available:
            try:
                price = int(str(p.get('price_aed', 0)).replace(',', ''))
            except:
                continue
            
            type_match = prop_type_lower in p.get('property_type', '').lower()
            city_match = city_lower in p.get('location', '').lower()
            budget_match = budget_min <= price <= budget_max
            
            if type_match and city_match and budget_match:
                # Calculate how close to user's exact budget
                price_diff = abs(price - budget)
                matches.append((price_diff, p))
        
        if matches:
            # Return the one closest to user's budget
            matches.sort(key=lambda x: x[0])
            return matches[0][1]
    
    # Priority 2: Type + City (any price)
    if prop_type and city:
        for p in available:
            type_match = prop_type_lower in p.get('property_type', '').lower()
            city_match = city_lower in p.get('location', '').lower()
            if type_match and city_match:
                return p
    
    # Priority 3: Type only
    if prop_type:
        for p in available:
            if prop_type_lower in p.get('property_type', '').lower():
                return p
    
    # Priority 4: City only
    if city:
        for p in available:
            if city_lower in p.get('location', '').lower():
                return p
    
    # Last resort: first available
    return available[0] if available else None


def find_alternative_properties(
    properties: List[Dict],
    prop_type: Optional[str] = None,
    city: Optional[str] = None,
    budget: Optional[int] = None,
    margin: int = 30000,
    max_results: int = 3,
    exclude_id: Optional[str] = None
) -> List[Dict]:
    """
    Find alternative properties within budget margin.
    
    Args:
        properties: List of all properties
        prop_type: Desired type
        city: Desired city
        budget: User's budget
        margin: ±AED amount (default 30,000)
        max_results: Maximum alternatives to return (default 3)
        exclude_id: Property ID to skip (the one already shown)
    
    Returns:
        List of up to max_results alternative properties
    """
    if not properties or not budget:
        return []
    
    budget_min = budget - margin
    budget_max = budget + margin
    
    prop_type_lower = (prop_type or "").lower()
    city_lower = (city or "").lower()
    
    alternatives = []
    
    for p in properties:
        # Skip sold
        if p.get('is_sold', False):
            continue
        
        # Skip excluded
        if exclude_id and str(p.get('id')) == str(exclude_id):
            continue
        
        # Parse price
        try:
            price = int(str(p.get('price_aed', 0)).replace(',', ''))
        except:
            continue
        
        # Apply filters
        if prop_type and prop_type_lower not in p.get('property_type', '').lower():
            continue
        if city and city_lower not in p.get('location', '').lower():
            continue
        if not (budget_min <= price <= budget_max):
            continue
        
        alternatives.append(p)
    
    # Sort by price (ascending - cheapest first)
    alternatives.sort(key=lambda p: int(str(p.get('price_aed', 0)).replace(',', '')))
    
    return alternatives[:max_results]


def format_property_caption(prop: Dict, include_roi: bool = True) -> str:
    """Build rich WhatsApp caption for a property"""
    lines = []
    
    # Header
    lines.append(f"📍 *{prop.get('name', 'Property')}*")
    
    # Price
    currency = prop.get('currency', 'AED')
    price = prop.get('price_aed', 'N/A')
    if isinstance(price, (int, float)):
        lines.append(f"💰 {currency} {price:,}")
    else:
        lines.append(f"💰 {currency} {price}")
    
    # Specs
    if prop.get('property_type'):
        lines.append(f"🏠 Type: {prop['property_type'].title()}")
    if prop.get('bedrooms') not in (None, 'N/A'):
        lines.append(f"🛏️ Bedrooms: {prop['bedrooms']}")
    if prop.get('bathrooms') not in (None, 'N/A'):
        lines.append(f"🚿 Bathrooms: {prop['bathrooms']}")
    if prop.get('area') not in (None, 'N/A'):
        try:
            area = int(prop['area'])
            lines.append(f"📐 Area: {area:,} sqft")
        except:
            lines.append(f"📐 Area: {prop['area']} sqft")
    
    # Investment details
    if include_roi and prop.get('roi') not in (None, 'N/A'):
        lines.append(f"📈 ROI: {prop['roi']}")
    if prop.get('emi_available'):
        lines.append(f"💳 EMI: Available")
    
    # Location
    if prop.get('location', '').strip():
        lines.append(f"📌 {prop['location'].strip()}")
    
    # Description
    if prop.get('description', '').strip():
        lines.append(f"\n📝 {prop['description'].strip()}")
    
    return "\n".join(lines)


def get_property_images(prop: Dict) -> List[str]:
    """Get all images for a property"""
    if prop.get('all_images'):
        return prop['all_images']
    if prop.get('image_url'):
        return [prop['image_url']]
    return []