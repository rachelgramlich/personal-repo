"""
Tidy First Practice Problems - Based on Kent Beck's "Tidy First?"

These are untidy code examples that need refactoring using the techniques
from the book. Try to refactor them yourself!
"""

from loguru import logger

# ============================================================================
# PROBLEM 1: Guard Clauses
# ============================================================================
# UNTIDY: Deeply nested if statements
# TRY TO FIX: Use guard clauses to flatten the structure
def calculate_discount_untidy(customer_type, purchase_amount, is_member):
    if customer_type == "retail":
        if purchase_amount > 100:
            if is_member:
                return 0.20
            else:
                return 0.15
        else:
            if is_member:
                return 0.10
            else:
                return 0.05
    else:
        if customer_type == "wholesale":
            if purchase_amount > 500:
                return 0.30
            else:
                return 0.25
        else:
            return 0.0

# TIDY: Refactored with guard clauses
def calculate_discount_tidy(customer_type, purchase_amount, is_member):
    if customer_type == "wholesale":
        return 0.25 if purchase_amount <= 500 else 0.30

    if customer_type == "retail":
        base_discount = 0.15 if purchase_amount > 100 else 0.05
        member_bonus = 0.05 if is_member else 0.0
        return base_discount + member_bonus

    return 0.0


# ============================================================================
# PROBLEM 2: Dead Code Elimination
# ============================================================================
# UNTIDY: Unused variables and commented-out code
# TRY TO FIX: Remove unused variables and dead code
def process_user_untidy(user_data):
    user_id = user_data["id"]
    user_name = user_data["name"]
    legacy_field = user_data.get("legacy_status")  # Never used
    # temp_value = 42  # Commented out code
    # print(f"Debug: {user_id}")  # Debug code left behind

    formatted_name = user_name.upper()
    return f"User: {formatted_name}"


# TIDY: Refactored by removing unused variables and commented-out code
def process_user_tidy(user_data):
    return f"User: {user_data['name'].upper()}"


# ============================================================================
# PROBLEM 3: Normalize Symmetries
# ============================================================================
# UNTIDY: Inconsistent patterns in similar code
# TRY TO FIX: Make similar operations consistent
def validate_email_untidy(email):
    if email is None:
        return False
    if email.strip() == "":
        return False
    if "@" not in email:
        return False
    return True


def validate_phone_untidy(phone):
    result = None
    if phone:
        result = True
    if not phone:
        result = False
    return result


def validate_email_tidy(email: str | None) -> bool:
    if not email:
        return False
    if email.strip() == "":
        return False
    if "@" not in email:
        return False
    return True


def validate_phone_tidy(phone: str | None) -> bool:
    if not phone:
        return False
    return True

# ============================================================================
# PROBLEM 4: Extract Helper Function
# ============================================================================
# UNTIDY: Complex calculation mixed with business logic
# TRY TO FIX: Extract helper functions to simplify the main function
def calculate_salary_untidy(hours_worked, hourly_rate, is_overtime):
    base = hours_worked * hourly_rate
    if is_overtime:
        tax = base * 0.25
        benefits = base * 0.08
    else:
        tax = base * 0.20
        benefits = base * 0.05
    net = base - tax - benefits
    return {"gross": base, "tax": tax, "benefits": benefits, "net": net}

def _calculate_tax_and_benefits(base, is_overtime):
    tax = base * 0.25 if is_overtime else base * 0.20
    benefits = base * 0.08 if is_overtime else base * 0.05
    return tax, benefits
    

def calculate_salary_tidy(hours_worked, hourly_rate, is_overtime):
    base = hours_worked * hourly_rate
    tax, benefits = _calculate_tax_and_benefits(base, is_overtime)
    net = base - tax - benefits
    return {"gross": base, "tax": tax, "benefits": benefits, "net": net}


# ============================================================================
# PROBLEM 5: Extract Variable (Magic Numbers)
# ============================================================================
# UNTIDY: Magic numbers scattered throughout
# TRY TO FIX: Extract magic numbers into named variables
def calculate_shipping_untidy(weight, distance, is_express):
    if weight > 50:
        base_cost = weight * 0.5
    else:
        base_cost = weight * 0.3

    distance_cost = distance * 0.01
    if is_express:
        distance_cost = distance * 0.02

    return base_cost + distance_cost + 5.0  # 5.0 is base fee

BASE_FEE = 5.0
HEAVY_WEIGHT_THRESHOLD = 50
HEAVY_WEIGHT_RATE = 0.5
LIGHT_WEIGHT_RATE = 0.3
STANDARD_DISTANCE_RATE = 0.01
EXPRESS_DISTANCE_RATE = 0.02


def calculate_shipping_tidy(weight, distance, is_express):
    weight_rate = HEAVY_WEIGHT_RATE if weight > HEAVY_WEIGHT_THRESHOLD else LIGHT_WEIGHT_RATE
    distance_rate = EXPRESS_DISTANCE_RATE if is_express else STANDARD_DISTANCE_RATE
    
    return (weight * weight_rate) + (distance * distance_rate) + BASE_FEE


# ============================================================================
# PROBLEM 6: Parting Parameterization
# ============================================================================
# UNTIDY: Duplicated logic with only values changing
# TRY TO FIX: Use parameterization to remove duplication
def apply_standard_discount_untidy(price):
    return price * 0.9


def apply_premium_discount_untidy(price):
    return price * 0.8


def apply_vip_discount_untidy(price):
    return price * 0.7

DISCOUNTS = {
    None: 1.0,
    "standard": 0.9,
    "premium": 0.8,
    "vip": 0.7
}

def apply_discount_tidy(price, discount_type: str | None):
    rate = DISCOUNTS.get(discount_type)
    return price * rate


# ============================================================================
# PROBLEM 7: Simplify Complex Conditionals
# ============================================================================
# UNTIDY: Complex boolean logic is hard to reason about
# TRY TO FIX: Use guard clauses and intermediate variables
def should_grant_access_untidy(user_role, is_active, account_balance):
    if user_role == "admin":
        return True
    else:
        if user_role == "user" and is_active and account_balance > 0:
            return True
        else:
            return False

def should_grant_access_tidy(user_role, is_active, account_balance):
    if user_role == "admin":
        return True
    
    if user_role != "user":
        return False
    
    if not is_active:
        return False
    
    has_sufficient_balance = account_balance > 0
    return has_sufficient_balance


# ============================================================================
# PROBLEM 8: Guard Clauses
# ============================================================================
# UNTIDY: Fix the following function using guard clauses
# Hint: Early returns can eliminate nesting!


def process_order_untidy(order):
                total = sum(item["price"] for item in order["items"])
                if total > 100:
                    return f"Large order: ${total}"
                else:
                    return f"Small order: ${total}"


LARGE_ORDER_THRESHOLD = 100

def process_order_tidy(order):
    if not order:
        return "No order provided"
    
    if "items" not in order:
        return "Invalid order format"
    
    if len(order["items"]) == 0:
        return "Order is empty"
    
    total = sum(item["price"] for item in order["items"])

    order_size = "Large" if total > LARGE_ORDER_THRESHOLD else "Small"
    
    return f"{order_size} order: ${total}"



# ============================================================================
# PROBLEM 9: Poor Naming
# ============================================================================
# UNTIDY: This function has poor naming. Refactor it.
# Hint: Rename variables meaningfully


def calc_cost_untidy(qty, uprice, shipcost, taxrate):
    subtotal = qty * uprice + shipcost
    final = subtotal * (1 + taxrate)
    return final

def calculate_cost_tidy(quantity, unit_price, shipping_cost, tax_rate):
    subtotal = (quantity * unit_price) + shipping_cost
    tax = subtotal * tax_rate
    return subtotal + tax


# ============================================================================
# PROBLEM 10: Extract Helper Functions
# ============================================================================
# UNTIDY: The email, phone, and age checks could be separate functions


def validate_user_profile_untidy(profile):
    # Check email
    if not profile.get("email"):
        return False
    email = profile["email"]
    if "@" not in email or "." not in email:
        return False

    # Check phone
    if not profile.get("phone"):
        return False
    phone = profile["phone"]
    if len(phone) < 10 or not phone.isdigit():
        return False

    # Check age
    if "age" not in profile:
        return False
    if profile["age"] < 18:
        return False

    return True

def _validate_email_tidy(email) -> bool:
    if "@" not in email or "." not in email:
        return False
    return True

def _validate_phone_tidy(phone) -> bool:
    if len(phone) < 10 or not phone.isdigit():
        return False
    return True

def _validate_age_tidy(age) -> bool:
    if age < 18:
        return False
    return True

def validate_user_profile_tidy(profile) -> bool:
    email = profile.get("email")
    phone = profile.get("phone")
    age = profile.get("age")

    if not all([email, phone, age]):
        return False

    return all([
        _validate_email_tidy(email),
        _validate_phone_tidy(phone),
        _validate_age_tidy(age)
    ])
