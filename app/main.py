from typing import TYPE_CHECKING

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.data_classes import S3Event
import boto3

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
    from aws_lambda_powertools.utilities.data_classes import SQSRecord
    from aws_lambda_powertools.utilities.typing import LambdaContext

processor = BatchProcessor(event_type=EventType.SQS)
logger = Logger()
metrics = Metrics()


def record_handler(record: SQSRecord) -> None:
    payload: dict = record.json_body
    s3_event = S3Event(payload)
    logger.info("Received S3 event", extra={"bucket_name": s3_event.bucket_name, "object_key": s3_event.object_key})

    s3_client = boto3.client("s3")
    try:
        response = s3_client.get_object(Bucket=s3_event.bucket_name, Key=s3_event.object_key)
        file_content = response["Body"].read()
        logger.info("Successfully read file from S3", extra={"file_size": len(file_content)})

        # Process the file content as needed
        # For example, you can parse it, transform it, or send it to another service
        metrics.add_metric(name="ProcessedFileSize", unit=MetricUnit.Bytes, value=response["ContentLength"])

    except Exception:
        logger.exception("Error processing S3 event")
        raise


@metrics.log_metrics
@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> PartialItemFailureResponse:
    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,
    )
