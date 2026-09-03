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


# --- PROBLEM 2 REFACTOR ---
def _format_currency_refactored(amount: float) -> float:
    return f"${amount:.2f}"


def _calculate_net_profit_refactored(revenue: float, expenses: float) -> float:
    return revenue - expenses


def generate_report_refactored(month: str, revenue: float, expenses: float) -> str:
    """Inline the small helper functions so this is readable in one glance."""
    report_title = f"Financial Report for {month}"
    profit = _calculate_net_profit_refactored(revenue, expenses)

    report = f"=== {report_title.upper()} ===\n"
    report += f"Revenue: {_format_currency_refactored(revenue)}\n"
    report += f"Expenses: {_format_currency_refactored(expenses)}\n"
    report += f"Net Profit: {_format_currency_refactored(profit)}\n"
    return report


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


# --- PROBLEM 3 REFACTOR ---
def _is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(email_regex, email))


def _is_strong_password(password: str) -> bool:
    """Validate password strength."""
    return len(password) >= 8 and any(char.isdigit() for char in password)


def _is_existing_user(email: str, db_connection) -> bool:
    """Check if user already exists in the database."""
    return db_connection.execute(f"SELECT * FROM users WHERE email='{email}'")


def _create_user(email: str, password: str, db_connection) -> None:
    """Create a new user in the database."""
    db_connection.execute(
        f"INSERT INTO users (email, password) VALUES ('{email}', '{password}')"
    )


def _send_welcome_email(email: str) -> None:
    """Send a welcome email to the new user."""
    email_body = f"Welcome to our platform, {email}! We are glad to have you."
    print(f"Sending email to {email}: {email_body}")


def register_user_refactored(user_data: dict, db_connection: object) -> dict:
    """
    Re-implement register_user.
    Extract helper functions as you see fit to balance readability!
    """
    email = user_data.get("email")
    password = user_data.get("password")

    if not email or not password:
        return {"status": "error", "message": "Missing email or password"}

    if not _is_valid_email(email):
        return {"status": "error", "message": "Invalid email format"}

    if not _is_strong_password(password):
        return {
            "status": "error",
            "message": "Password must be 8+ chars and contain a number",
        }

    if _is_existing_user(email, db_connection):
        return {"status": "error", "message": "User already exists"}

    _create_user(email, password, db_connection)
    _send_welcome_email(email)

    return {"status": "success", "message": "User created successfully"}
