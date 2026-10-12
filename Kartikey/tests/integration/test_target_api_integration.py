"""
Live integration test for the Applied Project target CRUD API.

This test calls the deployed API Gateway endpoint and verifies the
complete CRUD lifecycle against the real AWS infrastructure:

API Gateway -> Lambda -> DynamoDB

It is intentionally excluded from the normal unit/functional test
suite because it requires a deployed AWS environment.

AWS API Gateway Lambda proxy integration:
https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
"""

import json
import os
import urllib.error
import urllib.request

import pytest


RUN_LIVE_TESTS = os.environ.get("RUN_LIVE_TESTS") == "1"
TARGET_API_URL = os.environ.get(
    "TARGET_API_URL",
    "",
).rstrip("/")


pytestmark = pytest.mark.skipif(
    not RUN_LIVE_TESTS or not TARGET_API_URL,
    reason=(
        "Live integration test requires "
        "RUN_LIVE_TESTS=1 and TARGET_API_URL."
    ),
)


TEST_TARGET_ID = "integration-test-site"


def request(method, path, body=None):
    """Send a request to the deployed API Gateway endpoint."""

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    api_request = urllib.request.Request(
        f"{TARGET_API_URL}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            api_request,
            timeout=30,
        ) as response:
            response_body = json.loads(
                response.read().decode("utf-8")
            )

            return response.status, response_body

    except urllib.error.HTTPError as error:
        response_body = json.loads(
            error.read().decode("utf-8")
        )

        return error.code, response_body


def assert_timing(response_body):
    """Verify the API reports DynamoDB operation timing."""

    assert "operation_time_ms" in response_body
    assert isinstance(
        response_body["operation_time_ms"],
        (int, float),
    )
    assert response_body["operation_time_ms"] >= 0


def test_live_target_crud_lifecycle():
    """
    Verify Create, Read, Update and Delete against the
    real deployed Beta/Prod AWS API.
    """

    # Clean up a previous interrupted test if one exists.
    status, _ = request(
        "DELETE",
        f"/targets/{TEST_TARGET_ID}",
    )

    assert status in (200, 404)

    try:
        # ---------------------------------------------------------
        # CREATE
        # ---------------------------------------------------------
        status, created = request(
            "POST",
            "/targets",
            {
                "target_id": TEST_TARGET_ID,
                "name": "Integration Test Site",
                "url": "https://example.com",
            },
        )

        assert status == 201
        assert (
            created["target"]["target_id"]
            == TEST_TARGET_ID
        )
        assert (
            created["target"]["name"]
            == "Integration Test Site"
        )
        assert_timing(created)

        # ---------------------------------------------------------
        # READ
        # ---------------------------------------------------------
        status, read_result = request(
            "GET",
            f"/targets/{TEST_TARGET_ID}",
        )

        assert status == 200
        assert (
            read_result["target"]["target_id"]
            == TEST_TARGET_ID
        )
        assert (
            read_result["target"]["url"]
            == "https://example.com"
        )
        assert_timing(read_result)

        # ---------------------------------------------------------
        # UPDATE
        # ---------------------------------------------------------
        status, updated = request(
            "PUT",
            f"/targets/{TEST_TARGET_ID}",
            {
                "name": "Updated Integration Test Site",
                "url": "https://example.org",
            },
        )

        assert status == 200
        assert (
            updated["target"]["name"]
            == "Updated Integration Test Site"
        )
        assert (
            updated["target"]["url"]
            == "https://example.org"
        )
        assert_timing(updated)

        # ---------------------------------------------------------
        # READ UPDATED VALUE
        # ---------------------------------------------------------
        status, updated_read = request(
            "GET",
            f"/targets/{TEST_TARGET_ID}",
        )

        assert status == 200
        assert (
            updated_read["target"]["name"]
            == "Updated Integration Test Site"
        )
        assert (
            updated_read["target"]["url"]
            == "https://example.org"
        )
        assert_timing(updated_read)

        # ---------------------------------------------------------
        # DELETE
        # ---------------------------------------------------------
        status, deleted = request(
            "DELETE",
            f"/targets/{TEST_TARGET_ID}",
        )

        assert status == 200
        assert (
            deleted["target"]["target_id"]
            == TEST_TARGET_ID
        )
        assert_timing(deleted)

        # ---------------------------------------------------------
        # VERIFY DELETION
        # ---------------------------------------------------------
        status, missing = request(
            "GET",
            f"/targets/{TEST_TARGET_ID}",
        )

        assert status == 404
        assert missing["message"] == "Target not found."
        assert_timing(missing)

    finally:
        # Best-effort cleanup protects the real DynamoDB table if
        # an assertion fails halfway through the test.
        request(
            "DELETE",
            f"/targets/{TEST_TARGET_ID}",
        )