"""Starter ingredient catalog and a basic Indian home-cooking dish library.

Just a seed for `HomeChefApp.default_config()` — ingredients/dishes are added
from the admin UI as the family's real repertoire grows, and from then on the
stored config (not this file) is authoritative for what's been edited (see
ControllerState's per-key merge: once a list is saved, the file's copy wins).

Ingredients and dishes are referenced by name (unique, case-sensitive) rather
than a numeric id — there's no database here, just a JSON blob, and names are
natural keys for a catalog this size.
"""
from __future__ import annotations

CATEGORY_LABELS = {
    "vegetable": "Vegetables",
    "chicken": "Chicken",
    "fish": "Fish & Seafood",
    "egg": "Eggs",
    "paneer_dairy": "Paneer & Dairy",
    "lentil_pulse": "Lentils & Pulses",
    "grain_carb": "Grains & Carbs",
    "staple": "Pantry Staples",
}
CATEGORY_ORDER = list(CATEGORY_LABELS.keys())

# (name, category, is_staple)
_INGREDIENTS_RAW = [
    # Vegetables
    ("Onion", "vegetable", False),
    ("Tomato", "vegetable", False),
    ("Potato", "vegetable", False),
    ("Cauliflower", "vegetable", False),
    ("Spinach", "vegetable", False),
    ("Okra", "vegetable", False),
    ("Eggplant", "vegetable", False),
    ("Green Beans", "vegetable", False),
    ("Carrot", "vegetable", False),
    ("Peas", "vegetable", False),
    ("Capsicum", "vegetable", False),
    ("Cabbage", "vegetable", False),
    ("Bottle Gourd", "vegetable", False),
    ("Ridge Gourd", "vegetable", False),
    ("Methi Leaves", "vegetable", False),
    ("Ginger", "vegetable", False),
    ("Garlic", "vegetable", False),
    ("Green Chili", "vegetable", False),
    ("Lemon", "vegetable", False),
    ("Mint", "vegetable", False),
    # Chicken
    ("Chicken (Bone-in)", "chicken", False),
    ("Chicken Breast", "chicken", False),
    # Fish / seafood
    ("Fish Fillet", "fish", False),
    ("Prawns", "fish", False),
    # Egg
    ("Egg", "egg", False),
    # Paneer / dairy
    ("Paneer", "paneer_dairy", False),
    ("Yogurt", "paneer_dairy", False),
    ("Cream", "paneer_dairy", False),
    ("Butter/Ghee", "paneer_dairy", False),
    ("Milk", "paneer_dairy", False),
    ("Coconut", "paneer_dairy", False),
    # Lentils / pulses
    ("Toor Dal", "lentil_pulse", False),
    ("Moong Dal", "lentil_pulse", False),
    ("Masoor Dal", "lentil_pulse", False),
    ("Chana Dal", "lentil_pulse", False),
    ("Urad Dal", "lentil_pulse", False),
    ("Rajma", "lentil_pulse", False),
    ("Chickpeas", "lentil_pulse", False),
    # Grains / carbs
    ("Rice", "grain_carb", False),
    ("Wheat Flour (Atta)", "grain_carb", False),
    ("Poha", "grain_carb", False),
    ("Besan", "grain_carb", False),
    # Pantry staples - assumed on hand, excluded from "what's missing" by default
    ("Salt", "staple", True),
    ("Cooking Oil", "staple", True),
    ("Turmeric", "staple", True),
    ("Red Chili Powder", "staple", True),
    ("Coriander Powder", "staple", True),
    ("Cumin Seeds", "staple", True),
    ("Garam Masala", "staple", True),
    ("Mustard Seeds", "staple", True),
    ("Curry Leaves", "staple", True),
    ("Coriander Leaves", "staple", True),
    ("Bay Leaf", "staple", True),
    ("Hing", "staple", True),
]

INGREDIENTS = [{"name": n, "category": c, "is_staple": s} for n, c, s in _INGREDIENTS_RAW]

# (dish name, [ingredient names])
_DISHES_RAW = [
    ("Butter Chicken", ["Chicken Breast", "Tomato", "Onion", "Garlic", "Ginger", "Yogurt", "Cream", "Butter/Ghee"]),
    ("Chicken Curry", ["Chicken (Bone-in)", "Onion", "Tomato", "Garlic", "Ginger"]),
    ("Chicken Tikka Masala", ["Chicken Breast", "Yogurt", "Tomato", "Onion", "Cream"]),
    ("Chicken 65", ["Chicken Breast", "Yogurt", "Curry Leaves", "Green Chili"]),
    ("Chicken Biryani", ["Chicken (Bone-in)", "Rice", "Onion", "Yogurt", "Mint"]),
    ("Pepper Chicken Fry", ["Chicken (Bone-in)", "Onion", "Curry Leaves"]),
    ("Kadai Chicken", ["Chicken Breast", "Capsicum", "Onion", "Tomato"]),
    ("Chicken Korma", ["Chicken (Bone-in)", "Yogurt", "Onion", "Cream"]),
    ("Chicken Chettinad", ["Chicken (Bone-in)", "Onion", "Tomato", "Curry Leaves"]),
    ("Egg Curry", ["Egg", "Onion", "Tomato"]),
    ("Egg Bhurji", ["Egg", "Onion", "Tomato", "Capsicum"]),
    ("Fish Curry (Bengali Style)", ["Fish Fillet", "Mustard Seeds", "Tomato", "Onion"]),
    ("Fish Fry", ["Fish Fillet", "Lemon", "Green Chili"]),
    ("Goan Fish Curry", ["Fish Fillet", "Coconut", "Tomato", "Onion"]),
    ("Fish Tikka", ["Fish Fillet", "Yogurt", "Lemon"]),
    ("Prawn Curry", ["Prawns", "Onion", "Tomato", "Coconut"]),
    ("Prawn Masala", ["Prawns", "Onion", "Capsicum"]),
    ("Paneer Butter Masala", ["Paneer", "Tomato", "Cream", "Butter/Ghee"]),
    ("Palak Paneer", ["Paneer", "Spinach", "Onion", "Tomato"]),
    ("Matar Paneer", ["Paneer", "Peas", "Tomato", "Onion"]),
    ("Paneer Tikka", ["Paneer", "Capsicum", "Onion", "Yogurt"]),
    ("Aloo Gobi", ["Potato", "Cauliflower", "Onion", "Tomato"]),
    ("Bhindi Masala", ["Okra", "Onion", "Tomato"]),
    ("Baingan Bharta", ["Eggplant", "Onion", "Tomato"]),
    ("Methi Aloo", ["Methi Leaves", "Potato", "Onion"]),
    ("Lauki Sabzi", ["Bottle Gourd", "Onion", "Tomato"]),
    ("Cabbage Sabzi", ["Cabbage", "Onion", "Mustard Seeds"]),
    ("Mix Vegetable Curry", ["Potato", "Carrot", "Peas", "Green Beans", "Tomato", "Onion"]),
    ("Chana Masala", ["Chickpeas", "Onion", "Tomato"]),
    ("Rajma", ["Rajma", "Onion", "Tomato"]),
    ("Dal Tadka", ["Toor Dal", "Onion", "Tomato"]),
    ("Dal Makhani", ["Urad Dal", "Rajma", "Cream", "Butter/Ghee", "Tomato"]),
    ("Moong Dal Khichdi", ["Moong Dal", "Rice", "Onion"]),
    ("Saag", ["Spinach", "Methi Leaves", "Onion", "Garlic"]),
    ("Vegetable Pulao", ["Rice", "Peas", "Carrot", "Onion"]),
    ("Ridge Gourd Curry", ["Ridge Gourd", "Onion", "Tomato"]),
]

DISHES = [{"name": n, "ingredients": ings} for n, ings in _DISHES_RAW]
