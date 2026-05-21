"""
Smart Property Matcher - Intelligent Inventory Management
==========================================================
Handles complex matching scenarios with diplomatic responses:

1. Exact match found → show property
2. Within ±30k margin → show property
3. Budget too HIGH (no luxury inventory) → "all sold, will notify" 
4. Budget too LOW (under min available) → suggest minimum or notify
5. Type unavailable → redirect to alternatives
6. Out of stock → graceful handling

Author: Built for Aman Dominator's Sarah Bot
Version: 2.0 (Production - Smart Matching)
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchResult(Enum):
    """Possible outcomes when matching a property to user budget"""
    PERFECT_MATCH = "perfect_match"           # Found within ±30k
    BUDGET_TOO_HIGH = "budget_too_high"       # User has more money than our inventory
    BUDGET_TOO_LOW = "budget_too_low"         # User budget below our minimum
    NO_TYPE_MATCH = "no_type_match"           # Type not available
    NO_CITY_MATCH = "no_city_match"           # City not available
    INVENTORY_EMPTY = "inventory_empty"       # No properties available


class SmartPropertyMatcher:
    """
    Intelligent property matcher with diplomatic business logic.
    """
    
    DEFAULT_MARGIN = 30000  # ±30,000 AED
    
    def __init__(self, properties: List[Dict]):
        """Initialize with full property list"""
        self.all_properties = properties
        self.available = self._get_available()
        
    def _get_available(self) -> List[Dict]:
        """Get only unsold properties"""
        return [p for p in self.all_properties if not p.get('is_sold', False)]
    
    def _parse_price(self, prop: Dict) -> Optional[int]:
        """Safely parse property price as integer"""
        try:
            price = prop.get('price_aed', 0)
            if isinstance(price, str):
                price = price.replace(',', '').replace('AED', '').strip()
            return int(float(price))
        except (ValueError, TypeError):
            return None
    
    def get_inventory_stats(
        self, 
        prop_type: Optional[str] = None,
        city: Optional[str] = None
    ) -> Dict:
        """
        Get inventory statistics for filtered properties.
        Returns: min_price, max_price, count, types_available
        """
        prop_type_lower = (prop_type or "").lower()
        city_lower = (city or "").lower()
        
        # Filter by type and city
        filtered = []
        for p in self.available:
            if prop_type and prop_type_lower not in p.get('property_type', '').lower():
                continue
            if city and city_lower not in p.get('location', '').lower():
                continue
            price = self._parse_price(p)
            if price:
                filtered.append((price, p))
        
        if not filtered:
            return {
                'count': 0,
                'min_price': 0,
                'max_price': 0,
                'avg_price': 0,
                'types_available': self._get_available_types(),
                'cities_available': self._get_available_cities(),
            }
        
        prices = [p[0] for p in filtered]
        return {
            'count': len(filtered),
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': sum(prices) // len(prices),
            'properties': filtered,
            'types_available': self._get_available_types(),
            'cities_available': self._get_available_cities(),
        }
    
    def _get_available_types(self) -> List[str]:
        """Get list of unique property types in inventory"""
        types = set()
        for p in self.available:
            ptype = p.get('property_type', '').strip().title()
            if ptype:
                types.add(ptype)
        return sorted(list(types))
    
    def _get_available_cities(self, prop_type: Optional[str] = None) -> List[str]:
        """Get list of unique cities in inventory, optionally filtered by property type"""
        cities = set()
        prop_type_lower = (prop_type or "").lower()
        for p in self.available:
            # If a type filter is given, skip properties that don't match
            if prop_type and prop_type_lower not in p.get('property_type', '').lower():
                continue
            location = p.get('location', '')
            if location:
                parts = [pt.strip() for pt in location.split(',')]
                for part in parts:
                    common_cities = ['Dubai', 'Abu Dhabi', 'Sharjah', 'London',
                                    'Manchester', 'Birmingham', 'Delhi', 'Mumbai',
                                    'Bangalore', 'Kanpur', 'New Delhi']
                    for cc in common_cities:
                        if cc.lower() in part.lower():
                            cities.add(cc)
        return sorted(list(cities))
    
    def find_best_match(
        self,
        prop_type: Optional[str] = None,
        city: Optional[str] = None,
        budget: Optional[int] = None,
        margin: int = DEFAULT_MARGIN
    ) -> Tuple[MatchResult, Optional[Dict], Dict]:
        """
        Find best matching property with smart business logic.
        
        Returns: (MatchResult, best_property_or_None, context_dict)
        
        context_dict contains:
            - inventory_stats: details about inventory
            - suggested_budget: if mismatch, what budget would work
            - alternatives: list of alternatives if any
        """
        # Empty inventory check
        if not self.available:
            return MatchResult.INVENTORY_EMPTY, None, {}
        
        # Get filtered inventory stats
        stats = self.get_inventory_stats(prop_type=prop_type, city=city)
        
        # Type check
        if prop_type and prop_type.lower() not in [t.lower() for t in stats.get('types_available', [])]:
            return MatchResult.NO_TYPE_MATCH, None, {
                'requested_type': prop_type,
                'available_types': stats.get('types_available', [])
            }
        
        # No properties match type+city filter — figure out which dimension is the problem
        if stats['count'] == 0:
            # Get cities that DO have this property type (uses new type filter)
            cities_for_this_type = self._get_available_cities(prop_type=prop_type)
            return MatchResult.NO_CITY_MATCH, None, {
                'requested_city': city,
                'requested_type': prop_type,
                'cities_for_type': cities_for_this_type,        # cities where Commercial exists
                'available_cities': stats.get('cities_available', [])  # all cities (kept for compat)
            }
        
        # If no budget given, return cheapest match
        if not budget:
            cheapest = min(stats['properties'], key=lambda x: x[0])
            return MatchResult.PERFECT_MATCH, cheapest[1], {'inventory_stats': stats}
        
        budget_min = budget - margin
        budget_max = budget + margin
        
        # Find properties in range
        in_range = [
            (price, p) for price, p in stats['properties']
            if budget_min <= price <= budget_max
        ]
        
        if in_range:
            # Find closest to user's exact budget
            in_range.sort(key=lambda x: abs(x[0] - budget))
            return MatchResult.PERFECT_MATCH, in_range[0][1], {'inventory_stats': stats}
        
        # No match in range - figure out why
        if budget > stats['max_price'] + margin:
            # User has WAY more money than our inventory
            # Diplomatic response: "those were sold, will notify when new ones come"
            return MatchResult.BUDGET_TOO_HIGH, None, {
                'inventory_stats': stats,
                'user_budget': budget,
                'max_available': stats['max_price'],
                'suggested_explanation': 'sold_out_premium'
            }
        
        if budget < stats['min_price'] - margin:
            # Budget too low for our inventory
            return MatchResult.BUDGET_TOO_LOW, None, {
                'inventory_stats': stats,
                'user_budget': budget,
                'min_available': stats['min_price'],
            }
        
        # Edge case: budget close but no match (e.g., 500k requested, we have 460k & 550k)
        # Return closest available
        closest = min(stats['properties'], key=lambda x: abs(x[0] - budget))
        return MatchResult.PERFECT_MATCH, closest[1], {'inventory_stats': stats}
    
    def find_alternatives(
        self,
        prop_type: Optional[str] = None,
        city: Optional[str] = None,
        budget: Optional[int] = None,
        margin: int = DEFAULT_MARGIN,
        max_results: int = 3,
        exclude_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Find alternative properties within budget margin.
        Used when user dislikes first property shown.
        """
        if not budget:
            return []
        
        budget_min = budget - margin
        budget_max = budget + margin
        prop_type_lower = (prop_type or "").lower()
        city_lower = (city or "").lower()
        
        alternatives = []
        for p in self.available:
            # Skip excluded property
            if exclude_id and str(p.get('id')) == str(exclude_id):
                continue
            
            # Type filter
            if prop_type and prop_type_lower not in p.get('property_type', '').lower():
                continue
            
            # City filter
            if city and city_lower not in p.get('location', '').lower():
                continue
            
            # Budget filter
            price = self._parse_price(p)
            if price and budget_min <= price <= budget_max:
                alternatives.append((abs(price - budget), p))
        
        # Sort by closest to user's budget
        alternatives.sort(key=lambda x: x[0])
        return [alt[1] for alt in alternatives[:max_results]]
    
    def get_diplomatic_response(
        self,
        result: MatchResult,
        context: Dict,
        user_name: str = "there"
    ) -> str:
        """
        Get business-appropriate diplomatic message based on match result.
        Never says "we don't have" - always offers a graceful path forward.
        """
        title = self._get_title(user_name)
        
        if result == MatchResult.BUDGET_TOO_HIGH:
            stats = context.get('inventory_stats', {})
            return (
                f"{title}, thank you for sharing your budget! 🙏\n\n"
                f"We've had several premium properties in this range, but they "
                f"were all snapped up before your inquiry — they don't last long! 💎\n\n"
                f"We have new luxury listings coming in soon that match your "
                f"requirements. Could you please confirm your email so I can "
                f"notify you the moment they're available?\n\n"
                f"In the meantime, we have some excellent options at AED "
                f"{stats.get('max_price', 0):,} that offer fantastic value — "
                f"would you like to take a look at those? 😊"
            )
        
        if result == MatchResult.BUDGET_TOO_LOW:
            min_avail = context.get('min_available', 0)
            return (
                f"Thank you for sharing your budget! 🙏\n\n"
                f"Currently, our properties start at AED {min_avail:,}. Would you "
                f"be open to slightly adjusting your budget to explore these "
                f"premium options? They offer excellent ROI and lifestyle benefits.\n\n"
                f"Reply *yes* to see what's available at AED {min_avail:,}, or "
                f"share your email so I can notify you when properties in your "
                f"current range become available. 📧"
            )
        
        if result == MatchResult.NO_TYPE_MATCH:
            available_types = context.get('available_types', [])
            requested = context.get('requested_type', '')
            return (
                f"I completely understand — {requested}s are an excellent choice! 👍\n\n"
                f"However, I want to be upfront: at the moment, our portfolio "
                f"doesn't include {requested}s. We currently specialize in:\n"
                f"*{', '.join(available_types)}*\n\n"
                f"These offer a similar luxury lifestyle and strong ROI. Would "
                f"you be open to exploring one of these? Just reply with your "
                f"preferred type! 🏠"
            )
        
        if result == MatchResult.NO_CITY_MATCH:
            requested_type = context.get('requested_type', 'property')
            requested_city = context.get('requested_city', 'that city')
            cities_for_type = context.get('cities_for_type', [])
            
            if cities_for_type:
                # Type exists, but in different cities → offer those cities
                return (
                    f"Thank you for sharing your details! 🙏\n\n"
                    f"At the moment, we don't have *{requested_type}* listings in "
                    f"*{requested_city}* — but we do have great *{requested_type}* "
                    f"options available in:\n"
                    f"*{', '.join(cities_for_type)}*\n\n"
                    f"Would any of these locations work for you? Or I can have our "
                    f"consultant reach out personally with off-market options in "
                    f"{requested_city} when they become available! 📧"
                )
            
            # Type doesn't exist in any city → fall back to general handover
            return (
                f"Thank you for sharing your details! 🙏\n\n"
                f"At the moment, we don't have *{requested_type}* listings in "
                f"*{requested_city}*. Our consultant will personally reach out with "
                f"off-market options matching your requirements, and I'll notify you "
                f"the moment new {requested_type} listings become available! 📧"
            )
        
        if result == MatchResult.INVENTORY_EMPTY:
            return (
                f"Thank you for reaching out! 🙏\n\n"
                f"All our current listings have been booked, but we have exciting "
                f"new properties coming soon! Please share your email and I'll "
                f"personally notify you the moment new options are available. 📧"
            )
        
        return ""
    
    def _get_title(self, user_name: str) -> str:
        """Determine Mr./Ms. based on name"""
        first_name = user_name.split()[0] if user_name else "there"
        name_lower = first_name.lower()
        
        female_names = ['priya', 'aisha', 'fatima', 'sarah', 'maria', 'sara',
                       'mary', 'nisha', 'pooja', 'kavya', 'ananya', 'riya',
                       'anjali', 'meera', 'neha', 'divya', 'simran', 'sonia',
                       'ritu', 'shreya', 'tanya', 'aarti', 'manisha']
        male_names = ['aman', 'ahmed', 'john', 'raj', 'ali', 'mohammed',
                     'rohan', 'arjun', 'vikram', 'rahul', 'suresh', 'amit',
                     'rohit', 'karan', 'vivek', 'sumit', 'ravi', 'sandeep',
                     'manoj', 'deepak', 'ankit']
        
        if any(fn in name_lower for fn in female_names):
            return f"Ms. {first_name}"
        elif any(mn in name_lower for mn in male_names):
            return f"Mr. {first_name}"
        return first_name