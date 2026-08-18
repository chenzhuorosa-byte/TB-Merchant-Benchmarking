"""
Talabat restaurant detail page selectors — confirmed against a live detail page dump.
This is the ONLY file that knows about the detail page structure.

Primary data source: JSON-LD structured data embedded in the page
  <script type="application/ld+json">{"@type":"Restaurant", "address":…, "telephone":…}</script>

Secondary data source: data-testid attributes on HTML elements
  data-testid="restaurant-title"  → name + location
  data-testid="rest-status"       → open/closed text
  data-testid="cuisines"          → cuisine string
  data-testid="minimum-order"     → minimum order text
  data-testid="payemnt-method-wrapper" → payment methods (note: Talabat typo)
  data-testid="restaurant-rating-comp" → rating label
"""

# All fields available on the detail page.
# Drives the "From detail page" checkbox group in Step 2.
FIELDS = {
    "area": {
        "label":       "Area / Neighborhood",
        "description": "The area in Kuwait (e.g. Hawally, Salmiya, Mirqab)",
    },
    "address": {
        "label":       "Address",
        "description": "Street address of the restaurant",
    },
    "phone": {
        "label":       "Phone Number",
        "description": "Restaurant contact phone number",
    },
    "latitude": {
        "label":       "Latitude",
        "description": "GPS latitude coordinate",
    },
    "longitude": {
        "label":       "Longitude",
        "description": "GPS longitude coordinate",
    },
    "payment_methods": {
        "label":       "Payment Methods",
        "description": "Accepted payments (Visa, Mastercard, KNET, Cash)",
    },
    "open_status": {
        "label":       "Open Status",
        "description": "Whether the restaurant is currently open",
    },
}

# data-testid for the element containing the restaurant title and area text
TITLE_TESTID      = "restaurant-title"
# data-testid for open/closed status span
STATUS_TESTID     = "rest-status"
# data-testid for cuisine text (on detail page)
CUISINES_TESTID   = "cuisines"
# data-testid for the payment methods container (Talabat has a typo: 'payemnt')
PAYMENT_TESTID    = "payemnt-method-wrapper"
# Prefix of each individual payment method image testid
PAYMENT_IMG_PREFIX = "payment-image-"
# Rating component (same testid as on listing page)
RATING_TESTID     = "restaurant-rating-comp"

# Friendly display names for payment method slugs extracted from data-testid
PAYMENT_LABELS = {
    "visa_blue":        "Visa",
    "logo-mastercard":  "Mastercard",
    "logo-knet":        "KNET",
    "logo-cash":        "Cash",
}
