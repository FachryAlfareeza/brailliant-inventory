"""Local unit tests for src/app.py. No AWS account needed: DynamoDB is faked.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app  # noqa: E402


def _conditional_fail():
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException",
                                  "Message": "condition failed"}}, "op")


class FakeTable:
    """Just enough of the boto3 Table API for app.py."""

    def __init__(self):
        self.items = {}

        class _Client:
            def describe_table(_, TableName):
                return {"Table": {"TableStatus": "ACTIVE", "ItemCount": len(self.items)}}

        class _Meta:
            client = _Client()

        self.meta = _Meta()

    @staticmethod
    def _cond(expr):
        # Attr("partId").exists() / .not_exists() -> expression name
        return type(expr).__name__ if expr is not None else None

    def put_item(self, Item, ConditionExpression=None):
        if self._cond(ConditionExpression) == "AttributeNotExists" and Item["partId"] in self.items:
            raise _conditional_fail()
        self.items[Item["partId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["partId"])
        return {"Item": dict(item)} if item else {}

    def scan(self, FilterExpression=None, ExclusiveStartKey=None):
        items = list(self.items.values())
        if FilterExpression is not None:
            attr, value = FilterExpression._values
            items = [i for i in items if i.get(attr.name) == value]
        return {"Items": [dict(i) for i in items]}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression, ReturnValues):
        if Key["partId"] not in self.items:
            raise _conditional_fail()
        item = self.items[Key["partId"]]
        for name_key, field in ExpressionAttributeNames.items():
            item[field] = ExpressionAttributeValues[":" + name_key[1:]]
        return {"Attributes": dict(item)}

    def delete_item(self, Key, ConditionExpression=None):
        if Key["partId"] not in self.items:
            raise _conditional_fail()
        del self.items[Key["partId"]]


def call(route, body=None, part_id=None, query=None):
    event = {"routeKey": route}
    if body is not None:
        event["body"] = json.dumps(body)
    if part_id:
        event["pathParameters"] = {"partId": part_id}
    if query:
        event["queryStringParameters"] = query
    res = app.lambda_handler(event, None)
    return res["statusCode"], json.loads(res["body"])


class CrudTests(unittest.TestCase):
    def setUp(self):
        app._table = FakeTable()

    def test_full_crud_cycle(self):
        status, part = call("POST /parts", {
            "partId": "BOM-005", "section": "Carrier board", "reference": "U2",
            "description": "BQ25895RTWR charger", "qtyPerDevice": 1,
            "qtyInStock": 3, "unitCostLow": 1.06, "unitCostHigh": 2.23})
        self.assertEqual(status, 201)
        self.assertEqual(part["partId"], "BOM-005")

        status, body = call("GET /parts")
        self.assertEqual((status, body["count"]), (200, 1))

        status, body = call("GET /parts/{partId}", part_id="BOM-005")
        self.assertEqual((status, body["unitCostHigh"]), (200, 2.23))

        status, body = call("PUT /parts/{partId}", {"qtyInStock": 10, "location": "Bin A3"},
                            part_id="BOM-005")
        self.assertEqual((status, body["qtyInStock"], body["location"]), (200, 10, "Bin A3"))

        status, _ = call("DELETE /parts/{partId}", part_id="BOM-005")
        self.assertEqual(status, 200)
        status, _ = call("GET /parts/{partId}", part_id="BOM-005")
        self.assertEqual(status, 404)

    def test_generated_id_and_duplicate(self):
        status, part = call("POST /parts", {"description": "Speaker", "qtyInStock": 1})
        self.assertEqual(status, 201)
        self.assertTrue(part["partId"].startswith("P-"))
        status, _ = call("POST /parts", {"partId": part["partId"], "description": "x",
                                          "qtyInStock": 0})
        self.assertEqual(status, 409)

    def test_filter_by_section(self):
        call("POST /parts", {"partId": "A", "section": "Display PCB", "description": "a", "qtyInStock": 1})
        call("POST /parts", {"partId": "B", "section": "Carrier board", "description": "b", "qtyInStock": 1})
        status, body = call("GET /parts", query={"section": "Display PCB"})
        self.assertEqual([i["partId"] for i in body["items"]], ["A"])

    def test_validation(self):
        cases = [
            {"qtyInStock": 1},                                  # no description
            {"description": "x"},                               # no qty
            {"description": "x", "qtyInStock": -1},             # negative
            {"description": "x", "qtyInStock": 1.5},            # not integer
            {"description": "x", "qtyInStock": "3"},            # wrong type
            {"description": "x", "qtyInStock": 1, "price": 2},  # unknown field
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(call("POST /parts", body)[0], 400)
        self.assertEqual(app.lambda_handler({"routeKey": "POST /parts", "body": "{bad"}, None)["statusCode"], 400)

    def test_update_and_delete_missing(self):
        self.assertEqual(call("PUT /parts/{partId}", {"qtyInStock": 1}, part_id="nope")[0], 404)
        self.assertEqual(call("DELETE /parts/{partId}", part_id="nope")[0], 404)

    def test_health_and_unknown_route(self):
        self.assertEqual(call("GET /health")[0], 200)
        self.assertEqual(call("PATCH /parts")[0], 404)


if __name__ == "__main__":
    unittest.main()
