# Stores scan jobs as JSON files in an S3 bucket (scans/<scanId>.json), with the same
# few methods app.py uses on a DynamoDB table. Used in the AWS Academy lab, where
# DynamoDB isn't allowed but S3 is. Like DynamoDB on-demand, S3 is billed per request.
import json

from botocore.exceptions import ClientError

PREFIX = "scans/"


def _condition_failed():
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException",
                                  "Message": "item does not exist"}}, "S3Table")


class S3Table:
    def __init__(self, s3, bucket):
        self.s3 = s3
        self.bucket = bucket
        outer = self

        # app.py's health check calls table().meta.client.describe_table(...)
        class Client:
            def describe_table(self, TableName):
                outer.s3.head_bucket(Bucket=outer.bucket)
                return {"Table": {"TableStatus": "ACTIVE"}}

        class Meta:
            client = Client()

        self.meta = Meta()

    def _key(self, scan_id):
        return f"{PREFIX}{scan_id}.json"

    def _read(self, scan_id):
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._key(scan_id))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(obj["Body"].read())

    def _write(self, item):
        self.s3.put_object(Bucket=self.bucket, Key=self._key(item["scanId"]),
                           Body=json.dumps(item).encode(), ContentType="application/json")

    def put_item(self, Item, ConditionExpression=None):
        self._write(Item)

    def get_item(self, Key):
        item = self._read(Key["scanId"])
        return {"Item": item} if item else {}

    def scan(self, FilterExpression=None, ExclusiveStartKey=None):
        items = []
        pages = self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=PREFIX)
        for page in pages:
            for obj in page.get("Contents", []):
                scan_id = obj["Key"][len(PREFIX):-len(".json")]
                item = self._read(scan_id)
                if item:
                    items.append(item)
        if FilterExpression is not None:
            # only used as Attr("deviceId").eq(value)
            attr, value = FilterExpression._values
            items = [i for i in items if i.get(attr.name) == value]
        return {"Items": items}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression=None, ReturnValues=None):
        item = self._read(Key["scanId"])
        if item is None:
            raise _condition_failed()
        for name, field in ExpressionAttributeNames.items():
            item[field] = ExpressionAttributeValues[":" + name[1:]]
        self._write(item)
        return {"Attributes": item}

    def delete_item(self, Key, ConditionExpression=None):
        if self._read(Key["scanId"]) is None:
            raise _condition_failed()
        self.s3.delete_object(Bucket=self.bucket, Key=self._key(Key["scanId"]))
