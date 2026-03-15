import pytest
from loguru import logger
from src.python_practice.function_structure import (
    process_employee_data,
    process_employee_data_refactored,
    generate_report,
    generate_report_refactored,
    register_user,
    register_user_refactored,
)


@pytest.mark.parametrize(
    "raw_csv_line, expected",
    [
        (
            "John Doe,2022-10-15,Engineering,100000",
            {
                "name": "John Doe",
                "hire_date": "10/15/2022",
                "department": "Engineering",
                "total_compensation": 115000.0,
            },
        ),
        (
            "Jane Smith,2023-01-01,Sales,80000",
            {
                "name": "Jane Smith",
                "hire_date": "01/01/2023",
                "department": "Sales",
                "total_compensation": 96000.0,
            },
        ),
        ("Bad Row,Only Two", None),
        ("Bob,2020-05-05,InvalidDept,50000", None),
    ],
)
def test_p1_employee_data(raw_csv_line, expected):
    logger.info(f"Testing P1 with line: {raw_csv_line}")
    assert process_employee_data(raw_csv_line) == expected
    assert process_employee_data_refactored(raw_csv_line) == expected


def test_p2_generate_report():
    logger.info("Testing P2 report generation")
    args = ("October", 50000, 30000)
    expected = generate_report(*args)
    assert generate_report_refactored(*args) == expected


class MockDB:
    def execute(self, query):
        if "SELECT" in query and "existing@test.com" in query:
            return True
        return False


@pytest.mark.parametrize(
    "payload, expected_status",
    [
        ({"email": "new@test.com", "password": "StrongPassword1"}, "success"),
        ({"email": "existing@test.com", "password": "StrongPassword1"}, "error"),
        ({"email": "bademail", "password": "weak"}, "error"),
        ({"email": "", "password": ""}, "error"),
    ],
)
def test_p3_register_user(payload, expected_status):
    logger.info(f"Testing P3 with payload: {payload}")
    db = MockDB()
    expected = register_user(payload, db)
    assert expected["status"] == expected_status
    assert register_user_refactored(payload, db) == expected
