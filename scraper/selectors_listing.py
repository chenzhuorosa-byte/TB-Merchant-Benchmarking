"""
Talabat listing page selectors — confirmed against a live page dump.
This is the ONLY file that knows about the listing page structure.
"""

# data-testid of the <a> element that wraps each restaurant card
CARD_TESTID = "restaurant-a"

# data-testid of the rating component inside each card
RATING_TESTID = "restaurant-rating-comp"

# CSS class of the div that holds name, cuisine, and delivery info
CONTENT_CLASS = "content"

# URL query parameter used for pagination (?page=2, ?page=3, …)
PAGE_PARAM = "page"

# All fields available on the listing page.
# Drives the "From listing page" checkbox group in Step 2.
FIELDS = {
    "name": {
        "label":       "Restaurant Name",
        "description": "The name of the restaurant (e.g. KFC, Bartone)",
    },
    "cuisine": {
        "label":       "Cuisine Categories",
        "description": "Food types shown under the name (e.g. Fast Food, Pizza)",
    },
    "rating": {
        "label":       "Rating",
        "description": "Customer rating label (e.g. Amazing, Very good)",
    },
    "delivery_time": {
        "label":       "Delivery Time",
        "description": "Estimated delivery in minutes (e.g. 25 min)",
    },
    "delivery_fee": {
        "label":       "Delivery Fee",
        "description": "Cost of delivery (Free, or a KWD amount)",
    },
    "minimum_order": {
        "label":       "Minimum Order",
        "description": "Minimum basket value in KWD",
    },
}
