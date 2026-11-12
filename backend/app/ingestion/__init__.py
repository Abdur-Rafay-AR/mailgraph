# Ingestion package
from backend.app.ingestion.mime_parser import MimeParser, ParsedEmail, AddressInfo, AttachmentInfo
from backend.app.ingestion.pipeline import IngestionPipeline, IngestionResult

__all__ = ["MimeParser", "ParsedEmail", "AddressInfo", "AttachmentInfo", "IngestionPipeline", "IngestionResult"]
