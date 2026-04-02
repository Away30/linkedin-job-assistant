"""Test dry run mode."""
import pytest


def test_dry_run_field_in_schema(client):
    """AutomationStartRequest should accept dry_run field."""
    response = client.post("/api/v1/automation/start", json={
        "dry_run": True,
        "max_applies": 1,
    })
    # Should not 422 - field should be accepted
    assert response.status_code != 422
