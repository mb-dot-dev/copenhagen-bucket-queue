from __future__ import annotations

from unittest.mock import MagicMock, patch

from aws_lambda_powertools.metrics import MetricUnit
import pytest

from app.main import record_handler


def _make_sqs_record(bucket: str, key: str) -> MagicMock:
    record = MagicMock()
    record.json_body = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }
    return record


def test_record_handler_emits_file_size_bytes_metric() -> None:
    record = _make_sqs_record("my-bucket", "document.txt")

    mock_s3_response = {
        "ContentLength": 98765,
        "Body": MagicMock(read=MagicMock(return_value=b"")),
    }

    with (
        patch("app.main.boto3.client") as mock_boto3_client,
        patch("app.main.metrics.add_metric") as mock_add_metric,
    ):
        mock_boto3_client.return_value.get_object.return_value = mock_s3_response

        record_handler(record)

    mock_add_metric.assert_called_once_with(
        name="ProcessedFileSize",
        unit=MetricUnit.Bytes,
        value=98765,
    )


def test_record_handler_logs_error_on_exception() -> None:
    record = _make_sqs_record("my-bucket", "document.txt")

    with (
        patch("app.main.boto3.client") as mock_boto3_client,
        patch("app.main.logger.exception") as mock_logger_exception,
    ):
        mock_boto3_client.return_value.get_object.side_effect = Exception("S3 error")

        with pytest.raises(Exception, match="S3 error"):
            record_handler(record)

    mock_logger_exception.assert_called_once_with("Error processing S3 event")
