"""Tests for the DynamoDB statistics table contract."""

from dynamodb_stats_schema import (
    BILLING_MODE,
    BILLING_MODE_ON_DEMAND,
    GLOBAL_SECONDARY_INDEXES,
    GSI1PK,
    GSI1SK,
    PRESENT_MTIME_INDEX,
    SSE_SPECIFICATION,
    DynamoDBStatsTable,
)


def test_statistics_table_uses_on_demand_capacity_and_latest_uploads_index():
    request = DynamoDBStatsTable(table_name="dcstats-test").create_request()

    assert request[BILLING_MODE] == BILLING_MODE_ON_DEMAND
    assert request[GLOBAL_SECONDARY_INDEXES][0]["IndexName"] == PRESENT_MTIME_INDEX
    attributes = {attribute["AttributeName"] for attribute in request["AttributeDefinitions"]}
    assert {GSI1PK, GSI1SK}.issubset(attributes)
    assert request[SSE_SPECIFICATION] == {"Enabled": True, "SSEType": "KMS"}
