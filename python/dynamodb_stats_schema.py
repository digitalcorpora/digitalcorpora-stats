#!/usr/bin/env python3
"""Create the external DynamoDB table for DigitalCorpora statistics."""

from __future__ import annotations

import argparse
import os
from typing import Literal

import boto3
from botocore.client import BaseClient
from pydantic import BaseModel, Field

ATTRIBUTE_NAME = "AttributeName"
ATTRIBUTE_TYPE = "AttributeType"
ATTRIBUTE_DEFINITIONS = "AttributeDefinitions"
BILLING_MODE = "BillingMode"
BILLING_MODE_ON_DEMAND = "PAY_PER_REQUEST"
GLOBAL_SECONDARY_INDEXES = "GlobalSecondaryIndexes"
INDEX_NAME = "IndexName"
KEY_SCHEMA = "KeySchema"
KEY_TYPE = "KeyType"
KEY_TYPE_HASH = "HASH"
KEY_TYPE_RANGE = "RANGE"
PROJECTION = "Projection"
PROJECTION_TYPE = "ProjectionType"
PROJECTION_TYPE_ALL = "ALL"
SSE_ENABLED = "Enabled"
SSE_SPECIFICATION = "SSESpecification"
SSE_TYPE = "SSEType"
SSE_TYPE_KMS = "KMS"
TABLE_NAME = "TableName"
TAGS = "Tags"
TAG_KEY = "Key"
TAG_VALUE = "Value"

PK = "pk"
SK = "sk"
GSI1PK = "gsi1pk"
GSI1SK = "gsi1sk"
PRESENT_MTIME_INDEX = "present-mtime-index"


class AttributeDefinition(BaseModel):
    """One DynamoDB key attribute definition."""

    name: str
    attribute_type: Literal["S"] = "S"

    def aws(self) -> dict[str, str]:
        return {ATTRIBUTE_NAME: self.name, ATTRIBUTE_TYPE: self.attribute_type}


class KeyElement(BaseModel):
    """One hash or range key element."""

    name: str
    key_type: Literal["HASH", "RANGE"]

    def aws(self) -> dict[str, str]:
        return {ATTRIBUTE_NAME: self.name, KEY_TYPE: self.key_type}


class GlobalSecondaryIndex(BaseModel):
    """A DynamoDB global secondary index definition."""

    name: str
    partition_key: str
    sort_key: str

    def aws(self) -> dict[str, object]:
        return {
            INDEX_NAME: self.name,
            KEY_SCHEMA: [
                KeyElement(name=self.partition_key, key_type=KEY_TYPE_HASH).aws(),
                KeyElement(name=self.sort_key, key_type=KEY_TYPE_RANGE).aws(),
            ],
            PROJECTION: {PROJECTION_TYPE: PROJECTION_TYPE_ALL},
        }


class Tag(BaseModel):
    """One resource tag supplied to the DynamoDB API."""

    key: str
    value: str

    def aws(self) -> dict[str, str]:
        return {TAG_KEY: self.key, TAG_VALUE: self.value}


class DynamoDBStatsTable(BaseModel):
    """The external single-table schema for the statistics service."""

    table_name: str = Field(min_length=3)
    partition_key: str = PK
    sort_key: str = SK
    latest_uploads_index: GlobalSecondaryIndex = GlobalSecondaryIndex(
        name=PRESENT_MTIME_INDEX,
        partition_key=GSI1PK,
        sort_key=GSI1SK,
    )

    def create_request(self) -> dict[str, object]:
        attributes = [
            AttributeDefinition(name=self.partition_key).aws(),
            AttributeDefinition(name=self.sort_key).aws(),
            AttributeDefinition(name=self.latest_uploads_index.partition_key).aws(),
            AttributeDefinition(name=self.latest_uploads_index.sort_key).aws(),
        ]
        return {
            TABLE_NAME: self.table_name,
            ATTRIBUTE_DEFINITIONS: attributes,
            KEY_SCHEMA: [
                KeyElement(name=self.partition_key, key_type=KEY_TYPE_HASH).aws(),
                KeyElement(name=self.sort_key, key_type=KEY_TYPE_RANGE).aws(),
            ],
            BILLING_MODE: BILLING_MODE_ON_DEMAND,
            GLOBAL_SECONDARY_INDEXES: [self.latest_uploads_index.aws()],
            SSE_SPECIFICATION: {
                SSE_ENABLED: True,
                SSE_TYPE: SSE_TYPE_KMS,
            },
            TAGS: [
                Tag(key="Application", value="digitalcorpora-stats").aws(),
                Tag(key="ManagedBy", value="external-schema-program").aws(),
            ],
        }


def create_table(client: BaseClient, table: DynamoDBStatsTable, wait: bool) -> bool:
    """Create `table`; return False when it already exists."""
    try:
        client.describe_table(TableName=table.table_name)
    except client.exceptions.ResourceNotFoundException:
        client.create_table(**table.create_request())
        if wait:
            client.get_waiter("table_exists").wait(TableName=table.table_name)
        return True
    return False


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--table-name", default=os.getenv("DYNAMODB_STATS_TABLE"))
    result.add_argument("--region", default=os.getenv("AWS_REGION", "us-west-2"))
    result.add_argument("--endpoint-url", default=os.getenv("AWS_ENDPOINT_URL_DYNAMODB"))
    result.add_argument("--wait", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if not args.table_name:
        parser().error("--table-name or DYNAMODB_STATS_TABLE is required")
    client = boto3.client("dynamodb", region_name=args.region, endpoint_url=args.endpoint_url)
    table = DynamoDBStatsTable(table_name=args.table_name)
    created = create_table(client, table, args.wait)
    print(f"{'created' if created else 'exists'}: {table.table_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
