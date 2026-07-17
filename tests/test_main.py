from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from aws_lambda_powertools.metrics import MetricUnit

from app.main import lambda_handler

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext


def _make_sqs_record(message_id: str, bucket: str, key: str) -> dict:
    s3_event_body = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }
    return {
        "messageId": message_id,
        "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a",
        "body": json.dumps(s3_event_body),
        "attributes": {
            "ApproximateReceiveCount": "1",
            "SentTimestamp": "1545082649183",
            "SenderId": "AIDAIENQZJOLO23YVJ4VO",
            "ApproximateFirstReceiveTimestamp": "1545082649185",
        },
        "messageAttributes": {},
        "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
        "eventSource": "aws:sqs",
        "eventSourceARN": "arn:aws:sqs:eu-central-1:123456789012:my-queue",
        "awsRegion": "eu-central-1",
    }


def _make_sqs_event(bucket: str, key: str) -> dict:
    return {"Records": [_make_sqs_record("059f36b4-87a3-44ab-83d2-661975830a7d", bucket, key)]}


def test_lambda_handler_emits_file_size_bytes_metric(lambda_context: LambdaContext) -> None:
    event = _make_sqs_event("my-bucket", "document.txt")

    mock_s3_response = {
        "ContentLength": 98765,
        "Body": MagicMock(read=MagicMock(return_value=b"")),
    }

    with (
        patch("app.main.boto3.client") as mock_boto3_client,
        patch("app.main.metrics.add_metric") as mock_add_metric,
    ):
        mock_boto3_client.return_value.get_object.return_value = mock_s3_response

        response = lambda_handler(event, lambda_context)

    mock_add_metric.assert_called_once_with(
        name="ProcessedFileSize",
        unit=MetricUnit.Bytes,
        value=98765,
    )
    assert response["batchItemFailures"] == []


def test_lambda_handler_reports_batch_item_failure_on_exception(lambda_context: LambdaContext) -> None:
    event = {
        "Records": [
            _make_sqs_record("succeeding-message-id", "my-bucket", "ok.txt"),
            _make_sqs_record("failing-message-id", "my-bucket", "broken.txt"),
        ]
    }

    mock_s3_response = {
        "ContentLength": 98765,
        "Body": MagicMock(read=MagicMock(return_value=b"")),
    }

    with (
        patch("app.main.boto3.client") as mock_boto3_client,
        patch("app.main.logger.exception") as mock_logger_exception,
    ):
        mock_boto3_client.return_value.get_object.side_effect = [
            mock_s3_response,
            Exception("S3 error"),
        ]

        response = lambda_handler(event, lambda_context)

    mock_logger_exception.assert_called_once_with("Error processing S3 event")
    assert response["batchItemFailures"] == [{"itemIdentifier": "failing-message-id"}]
