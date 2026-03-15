"""
PRACTICE PROBLEM SET: Function Structure

Instructions:
Refactor the following functions based on the principles of 
single responsibility, abstraction, and avoiding unnecessary indirection.

Feel free to add new functions or remove existing ones to make the 
code as readable and maintainable as possible.
"""

import re

# =====================================================================
# PROBLEM 1: The "Everything and the Kitchen Sink" Function
# 
# CONSIDERATION: This function violates the "One Goal" rule and mixes 
# levels of abstraction. It reads a raw string, parses it, validates it, 
# formats data, and does math.
#
# YOUR TASK: Extract the smaller logical chunks into their own 
# functions so that `process_employee_data` reads like a high-level 
# summary of what is happening.
# =====================================================================

def process_employee_data(raw_csv_line):
    # 1. Parse the line
    parts = raw_csv_line.strip().split(',')
    if len(parts) != 4:
        return None
        
    name = parts[0]
    raw_date = parts[1]
    department = parts[2]
    salary_str = parts[3]
    
    # 2. Validate department
    valid_departments = ['Engineering', 'Sales', 'Marketing', 'HR']
    if department not in valid_departments:
        print(f"Error: Invalid department {department}")
        return None
        
    # 3. Format the date (from YYYY-MM-DD to DD/MM/YYYY)
    date_parts = raw_date.split('-')
    if len(date_parts) == 3:
        formatted_date = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
    else:
        formatted_date = "Unknown"
        
    # 4. Calculate bonus based on department
    base_salary = float(salary_str)
    if department == 'Engineering':
        bonus = base_salary * 0.15
    elif department == 'Sales':
        bonus = base_salary * 0.20
    else:
        bonus = base_salary * 0.05
        
    return {
        "name": name,
        "hire_date": formatted_date,
        "department": department,
        "total_compensation": base_salary + bonus
    }

# --- PROBLEM 1 PLACEHOLDERS ---
def process_employee_data_refactored(raw_csv_line):
    """
    Re-implement process_employee_data. 
    Create your own helper functions above this one as you see fit!
    """
    pass


# =====================================================================
# PROBLEM 2: Spaghetti by Abstraction (Too much indirection)
# 
# CONSIDERATION: Someone took "small functions" too literally. 
# There is so much jumping around that it's hard to tell what the 
# code actually does. The abstraction isn't hiding complexity; 
# it's just hiding the code.
#
# YOUR TASK: Inline the unnecessary functions back into `generate_report`
# to make it readable in a single glance.
# =====================================================================

def get_report_title(month):
    return f"Financial Report for {month}"

def format_currency(amount):
    return f"${amount:.2f}"

def calculate_net_profit(revenue, expenses):
    return revenue - expenses

def generate_report_header(month):
    title = get_report_title(month)
    return f"=== {title.upper()} ==="

def generate_report(month, revenue, expenses):
    header = generate_report_header(month)
    profit = calculate_net_profit(revenue, expenses)
    formatted_profit = format_currency(profit)
    formatted_revenue = format_currency(revenue)
    formatted_expenses = format_currency(expenses)
    
    report = f"{header}\n"
    report += f"Revenue: {formatted_revenue}\n"
    report += f"Expenses: {formatted_expenses}\n"
    report += f"Net Profit: {formatted_profit}\n"
    return report

# --- PROBLEM 2 PLACEHOLDER ---
def generate_report_refactored(month, revenue, expenses):
    """Inline the small helper functions so this is readable in one glance."""
    pass


# =====================================================================
# PROBLEM 3: The Balancing Act
# 
# CONSIDERATION: This is a realistic web-backend style function. 
# It handles a new user signup. It's not terrible, but it could be 
# tidier. You need to decide what to extract and what to leave inline.
#
# YOUR TASK: Refactor `register_user`. Create helper functions where 
# they make the main flow clearer, but don't over-engineer it. 
# (Assume database and email functions are mocked).
# =====================================================================

def register_user(user_data, db_connection):
    # Validate payload
    if not user_data.get('email') or not user_data.get('password'):
        return {"status": "error", "message": "Missing email or password"}
    
    # Validate email format
    email = user_data['email']
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        return {"status": "error", "message": "Invalid email format"}
        
    # Validate password strength
    password = user_data['password']
    if len(password) < 8 or not any(char.isdigit() for char in password):
        return {"status": "error", "message": "Password must be 8+ chars and contain a number"}
        
    # Check if user exists (mocked DB call)
    existing_user = db_connection.execute(f"SELECT * FROM users WHERE email='{email}'")
    if existing_user:
        return {"status": "error", "message": "User already exists"}
        
    # Create user (mocked DB call)
    db_connection.execute(f"INSERT INTO users (email, password) VALUES ('{email}', '{password}')")
    
    # Send welcome email (mocked network call)
    email_body = f"Welcome to our platform, {email}! We are glad to have you."
    print(f"Sending email to {email}: {email_body}")
    
    return {"status": "success", "message": "User created successfully"}

# --- PROBLEM 3 PLACEHOLDERS ---
def register_user_refactored(user_data, db_connection):
    """
    Re-implement register_user. 
    Extract helper functions as you see fit to balance readability!
    """
    pass


# =====================================================================
# TESTS TO ENSURE YOUR REFACTORS MATCH THE ORIGINAL BEHAVIOR
# =====================================================================
def run_tests():
    print("Running tests...\n")

    # Test Problem 1
    print("Testing Problem 1...")
    p1_input = "John Doe,2022-10-15,Engineering,100000"
    expected_p1 = process_employee_data(p1_input)
    actual_p1 = process_employee_data_refactored(p1_input)
    assert actual_p1 == expected_p1, f"Expected {expected_p1}, but got {actual_p1}"
    print("Problem 1 tests passed!\n")

    # Test Problem 2
    print("Testing Problem 2...")
    expected_p2 = generate_report("October", 50000, 30000)
    actual_p2 = generate_report_refactored("October", 50000, 30000)
    assert actual_p2 == expected_p2, "Problem 2 refactored output does not match original"
    print("Problem 2 tests passed!\n")

    # Test Problem 3
    print("Testing Problem 3...")
    class MockDB:
        def execute(self, query):
            if "SELECT" in query and "existing@test.com" in query:
                return True
            return False
    
    db = MockDB()
    valid_payload = {"email": "new@test.com", "password": "StrongPassword1"}
    expected_p3 = register_user(valid_payload, db)
    actual_p3 = register_user_refactored(valid_payload, db)
    assert actual_p3 == expected_p3, "Problem 3 valid user logic failed"
    
    invalid_payload = {"email": "bademail", "password": "weak"}
    assert register_user_refactored(invalid_payload, db) == register_user(invalid_payload, db), "Problem 3 invalid user logic failed"
    print("Problem 3 tests passed!\n")

    print("🎉 ALL TESTS PASSED! Your refactored code is tidy AND correct.")

if __name__ == "__main__":
    # Remove the 'pass' and uncomment 'run_tests()' when you are ready to test!
    pass
    # run_tests()