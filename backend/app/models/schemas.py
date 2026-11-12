"""Pydantic request and response schemas for MailGraph API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AccountCreate(BaseModel):
    provider: str  # 'synthetic', 'mbox', 'imap', 'gmail'
    display_name: str
    email_address: str
    settings_json: Optional[str] = "{}"

class AccountResponse(BaseModel):
    id: int
    provider: str
    display_name: str
    email_address: str
    created_at: str
    last_sync_at: Optional[str] = None
    status: str

class SyntheticGenerateRequest(BaseModel):
    display_name: str = "Demo Mailbox"
    email_address: str = "demo@mailgraph.local"
    message_count: int = 50
    seed: int = 42

class ImapConnectRequest(BaseModel):
    display_name: str
    email_address: str
    host: str
    username: str
    password: str
    port: int = 993
    use_ssl: bool = True

class GmailConnectRequest(BaseModel):
    display_name: str
    email_address: str
    client_id: str
    client_secret: str

class QueryConditionSchema(BaseModel):
    field: str
    op: str
    value: Any

class QueryASTSchema(BaseModel):
    version: int = 1
    account_ids: Optional[List[int]] = None
    all: List[QueryConditionSchema] = Field(default_factory=list)
    any: List[QueryConditionSchema] = Field(default_factory=list)
    none: List[QueryConditionSchema] = Field(default_factory=list)
    search_term: Optional[str] = None
    exclude_protected: bool = True

class MessageSearchRequest(BaseModel):
    query: QueryASTSchema = Field(default_factory=QueryASTSchema)
    page: int = 1
    page_size: int = 50
    sort_by: str = "received_at"
    sort_dir: str = "DESC"

class SenderProtectRequest(BaseModel):
    is_protected: bool

class BulkSenderCleanupRequest(BaseModel):
    sender_ids: List[int]
    operation_type: str  # 'trash' or 'archive'
    exclude_protected: bool = True

class CleanupPreviewRequest(BaseModel):
    account_id: Optional[int] = None
    operation_type: str = "trash"
    query: QueryASTSchema

class CleanupExecuteRequest(BaseModel):
    account_id: Optional[int] = None
    operation_type: str = "trash"
    query: QueryASTSchema

class CleanupUndoRequest(BaseModel):
    operation_id: int

class ProtectionRuleCreate(BaseModel):
    account_id: Optional[int] = None
    rule_type: str  # 'sender', 'domain', 'message'
    rule_value: str
    reason: Optional[str] = None

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    index_message_bodies: Optional[bool] = None
    local_ai_enabled: Optional[bool] = None
    local_ai_endpoint: Optional[str] = None
    local_ai_model: Optional[str] = None
    default_delete_mode: Optional[str] = None

class NlQueryRequest(BaseModel):
    prompt: str
