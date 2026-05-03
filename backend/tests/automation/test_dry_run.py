"""Test dry run mode."""
from app.schemas.schemas import AutomationStartRequest


def test_dry_run_field_in_schema():
    """AutomationStartRequest should accept dry_run field."""
    request = AutomationStartRequest(
        dry_run=True,
        max_applies=1,
    )

    assert request.dry_run is True
    assert request.max_applies == 1
