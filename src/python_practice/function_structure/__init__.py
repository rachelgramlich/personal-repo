"""
PRACTICE PROBLEM SET: Function Structure

Instructions:
Refactor the following functions based on the principles of
single responsibility, abstraction, and avoiding unnecessary indirection.

Feel free to add new functions or remove existing ones to make the
code as readable and maintainable as possible.
"""

from datetime import datetime
from loguru import logger
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
    parts = raw_csv_line.strip().split(",")
    if len(parts) != 4:
        return None

    name = parts[0]
    raw_date = parts[1]
    department = parts[2]
    salary_str = parts[3]

    # 2. Validate department
    valid_departments = ["Engineering", "Sales", "Marketing", "HR"]
    if department not in valid_departments:
        print(f"Error: Invalid department {department}")
        return None

    # 3. Format the date (from YYYY-MM-DD to DD/MM/YYYY)
    date_parts = raw_date.split("-")
    if len(date_parts) == 3:
        formatted_date = f"{date_parts[1]}/{date_parts[2]}/{date_parts[0]}"
    else:
        formatted_date = "Unknown"

    # 4. Calculate bonus based on department
    base_salary = float(salary_str)
    if department == "Engineering":
        bonus = base_salary * 0.15
    elif department == "Sales":
        bonus = base_salary * 0.20
    else:
        bonus = base_salary * 0.05

    return {
        "name": name,
        "hire_date": formatted_date,
        "department": department,
        "total_compensation": base_salary + bonus,
    }


# --- PROBLEM 1 REFACTOR ---
## Move sections into helper functions
def _parse_csv_line(raw_csv_line: str) -> tuple[str, str, str, str]:
    """Parse the raw CSV line and return the components."""
    parts = raw_csv_line.strip().split(",")
    if len(parts) != 4:
        return None

    name = parts[0]
    raw_date = parts[1]
    department = parts[2]
    salary_str = parts[3]

    return name, raw_date, department, salary_str


def _validate_department(department: str) -> None:
    """Check if department is in valid list."""
    valid_departments = ["Engineering", "Sales", "Marketing", "HR"]
    if department not in valid_departments:
        print(f"Error: Invalid department {department}")
        return None

    return department


def _format_date(raw_date: str) -> str:
    """Convert date from YYYY-MM-DD to MM/DD/YYYY format."""
    date_parts = raw_date.split("-")
    if len(date_parts) == 3:
        formatted_date = f"{date_parts[1]}/{date_parts[2]}/{date_parts[0]}"
    else:
        formatted_date = "Unknown"

    return formatted_date


def _calculate_bonus_by_department(salary_str: str, department: str) -> float:
    """Calculate bonus based on department."""
    base_salary = float(salary_str)
    if department == "Engineering":
        bonus = base_salary * 0.15
    elif department == "Sales":
        bonus = base_salary * 0.20
    else:
        bonus = base_salary * 0.05

    return base_salary, bonus


## Refactor helper functions tidier


def _parse_csv_line_refactored(raw_csv_line: str) -> tuple[str, str, str, str]:
    """Parse the raw CSV line and return the components."""
    parts = raw_csv_line.strip().split(",")
    if len(parts) != 4:
        # Better: raise an exception instead of returning None
        return None

    name = parts[0]
    raw_date = parts[1]
    department = parts[2]
    salary_str = parts[3]

    return name, raw_date, department, salary_str


def is_valid_department_refactored(department: str) -> bool:
    """Check if department is in valid list."""
    VALID_DEPARTMENTS = ["Engineering", "Sales", "Marketing", "HR"]

    if department not in VALID_DEPARTMENTS:
        logger.error(f"Invalid department {department}")
        return False
    return True


def _format_date_refactored(raw_date: str) -> datetime:
    """Convert date from YYYY-MM-DD to DD/MM/YYYY format."""
    original_date_object = datetime.strptime(raw_date, "%Y-%m-%d")
    return original_date_object.strftime("%m/%d/%Y")


def _calculate_compensation_by_department_refactored(
    salary_str: str, department: str
) -> float:
    """Calculate total compensation based on department."""
    DEPARTMENT_BONUS_RATES = {
        "Engineering": 0.15,
        "Sales": 0.20,
    }
    STANDARD_BONUS_RATE = 0.05

    base_salary = float(salary_str)
    bonus_rate = DEPARTMENT_BONUS_RATES.get(department, STANDARD_BONUS_RATE)
    bonus = base_salary * bonus_rate

    total_compensation = base_salary + bonus

    return total_compensation


def process_employee_data_refactored(
    raw_csv_line: str,
) -> dict[str, datetime, str, float] | None:
    """
    Re-implement process_employee_data.
    Create your own helper functions above this one as you see fit!
    """
    parsed_data = _parse_csv_line_refactored(raw_csv_line)
    if not parsed_data:
        # Better: raise an exception instead of returning None
        return None

    name, raw_date, department, salary_str = parsed_data

    if not is_valid_department_refactored(department):
        return None

    formatted_date = _format_date_refactored(raw_date)

    total_compensation = _calculate_compensation_by_department_refactored(
        salary_str, department
    )

    return {
        "name": name,
        "hire_date": formatted_date,
        "department": department,
        "total_compensation": total_compensation,
    }


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
    if not user_data.get("email") or not user_data.get("password"):
        return {"status": "error", "message": "Missing email or password"}

    # Validate email format
    email = user_data["email"]
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        return {"status": "error", "message": "Invalid email format"}

    # Validate password strength
    password = user_data["password"]
    if len(password) < 8 or not any(char.isdigit() for char in password):
        return {
            "status": "error",
            "message": "Password must be 8+ chars and contain a number",
        }

    # Check if user exists (mocked DB call)
    existing_user = db_connection.execute(f"SELECT * FROM users WHERE email='{email}'")
    if existing_user:
        return {"status": "error", "message": "User already exists"}

    # Create user (mocked DB call)
    db_connection.execute(
        f"INSERT INTO users (email, password) VALUES ('{email}', '{password}')"
    )

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
    assert (
        actual_p2 == expected_p2
    ), "Problem 2 refactored output does not match original"
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
    assert register_user_refactored(invalid_payload, db) == register_user(
        invalid_payload, db
    ), "Problem 3 invalid user logic failed"
    print("Problem 3 tests passed!\n")

    print("🎉 ALL TESTS PASSED! Your refactored code is tidy AND correct.")


if __name__ == "__main__":
    # Remove the 'pass' and uncomment 'run_tests()' when you are ready to test!
    pass
    # run_tests()


# =====================================================================
# EXECUTION BLOCK (Run the functions to see them work)
# =====================================================================


if __name__ == "__main__":
    logger.info("RUNNING PROBLEM 1: Employee Data")
    csv_line = "John Doe,2022-10-15,Engineering,100000"
    logger.info(f"Input: {csv_line}")
    result_p1 = process_employee_data(csv_line)
    logger.info(f"Original Output:\n{result_p1}")
    result_p1_ref = process_employee_data_refactored(csv_line)
    logger.info(f"Refactored Output:\n{result_p1_ref}\n")

    logger.info("RUNNING PROBLEM 2: Generate Report")
    result_p2 = generate_report("October", 50000, 30000)
    logger.info("Original Output:")
    logger.info(f"\n{result_p2}")
    result_p2_ref = generate_report_refactored("October", 50000, 30000)
    logger.info("Refactored Output:")
    logger.info(f"\n{result_p2_ref}\n")

    logger.info("RUNNING PROBLEM 3: Register User")

    class MockDB:
        def execute(self, query):
            logger.debug(f"[DB Mock executing]: {query}")
            return False  # Simulates that the user does not exist yet

    db = MockDB()
    payload = {"email": "new@test.com", "password": "StrongPassword1"}
    logger.info(f"Input Payload: {payload}")
    result_p3 = register_user(payload, db)
    logger.info(f"Original Output:\n{result_p3}")
    result_p3_ref = register_user_refactored(payload, db)
    logger.info(f"Refactored Output:\n{result_p3_ref}\n")
