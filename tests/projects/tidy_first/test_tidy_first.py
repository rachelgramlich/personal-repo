import pytest
from projects.tidy_first import *

@pytest.mark.parametrize("customer_type, amount, member, expected", [
    ("retail", 150, True, 0.20),
    ("retail", 50, False, 0.05),
    ("wholesale", 600, False, 0.30),
    ("unknown", 100, True, 0.0),
])
def test_p1_discount(customer_type, amount, member, expected):
    assert calculate_discount_untidy(customer_type, amount, member) == expected
    assert calculate_discount_tidy(customer_type, amount, member) == expected

def test_p2_user_process():
    data = {'id': 1, 'name': 'john'}
    expected = "User: JOHN"
    assert process_user_untidy(data) == expected
    assert process_user_tidy(data) == expected

@pytest.mark.parametrize("email, expected", [
    ("test@ex.com", True),
    ("invalid", False),
    ("", False),
    (None, False),
])
def test_p3_email(email, expected):
    assert validate_email_untidy(email) == expected
    assert validate_email_tidy(email) == expected

def test_p4_salary():
    args = (40, 25, True)
    assert calculate_salary_untidy(*args) == calculate_salary_tidy(*args)

def test_p5_shipping():
    args = (60, 200, True)
    assert calculate_shipping_untidy(*args) == calculate_shipping_tidy(*args)

def test_p6_discount_symmetry():
    price = 100
    assert apply_standard_discount_untidy(price) == apply_discount_tidy(price, "standard")

@pytest.mark.parametrize("role, active, balance, expected", [
    ("admin", False, -100, True),
    ("user", True, 50, True),
    ("user", False, 50, False),
    ("guest", True, 1000, False),
])
def test_p7_access(role, active, balance, expected):
    assert should_grant_access_untidy(role, active, balance) == expected
    assert should_grant_access_tidy(role, active, balance) == expected

def test_p8_orders():
    order = {"items": [{"price": 50}, {"price": 75}]}
    assert process_order_untidy(order) == "Large order: $125"
    assert "Large order" in process_order_tidy(order)

def test_p9_naming():
    args = (5, 20, 10, 0.08)
    # Requires explicit rounding to avoid floating-point precision issues
    assert round(calc_cost_untidy(*args), 2) == round(calculate_cost_tidy(*args), 2)

def test_p10_profile():
    profile = {"email": "dev@test.com", "phone": "1234567890", "age": 25}
    assert validate_user_profile_untidy(profile) == validate_user_profile_tidy(profile)