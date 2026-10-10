import pytest

from app.attendance import calculate_attendance


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        (
            [
                {
                    "subject_code": "ZERO",
                    "subject_name": "No Classes Yet",
                    "attended_classes": 0,
                    "total_classes": 0,
                }
            ],
            0.0,
        ),
        (
            [
                {
                    "subject_code": "NORM",
                    "subject_name": "Normal Attendance",
                    "attended_classes": 3,
                    "total_classes": 4,
                }
            ],
            75.0,
        ),
        (
            [
                {
                    "subject_code": "FULL",
                    "subject_name": "Full Attendance",
                    "attended_classes": 8,
                    "total_classes": 8,
                }
            ],
            100.0,
        ),
    ],
)
def test_attendance_percentage_calculation(records, expected):
    report = calculate_attendance("DEMO1234", records)

    assert report["subjects"][0]["percentage"] == expected


def test_attendance_calculation_rejects_invalid_student_id():
    with pytest.raises(ValueError, match="fictional DEMO"):
        calculate_attendance("STUDENT1", [])
