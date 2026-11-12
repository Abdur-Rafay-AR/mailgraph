"""Safe RFC822 / MIME email parser."""

import os
import re
import hashlib
import email
from email import policy
from email.utils import parseaddr, getaddresses, parsedate_to_datetime
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class AddressInfo:
    address: str
    display_name: str
    role: str  # 'from', 'to', 'cc', 'bcc', 'reply_to'

@dataclass
class AttachmentInfo:
    filename: str
    mime_type: str
    size_bytes: int
    content_hash: Optional[str] = None
    is_inline: bool = False
    content_available: bool = False
    data: Optional[bytes] = None

@dataclass
class ParsedEmail:
    provider_message_id: str
    provider_thread_id: Optional[str] = None
    message_id_header: Optional[str] = None
    in_reply_to: Optional[str] = None
    references_header: Optional[str] = None
    subject: str = "(No Subject)"
    sender_name: str = ""
    sender_address: str = "unknown@unknown"
    sender_domain: str = "unknown"
    sent_at: Optional[str] = None
    received_at: str = ""
    is_read: bool = False
    is_starred: bool = False
    is_important: bool = False
    has_attachments: bool = False
    size_bytes: int = 0
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    content_hash: str = ""
    addresses: List[AddressInfo] = field(default_factory=list)
    attachments: List[AttachmentInfo] = field(default_factory=list)
    headers_dict: dict = field(default_factory=dict)

def sanitize_filename(filename: Optional[str]) -> str:
    """Sanitize attachment filename to prevent path traversal or filesystem escapes."""
    if not filename:
        return "attachment.bin"
    # Take only the base filename
    cleaned = os.path.basename(filename.replace("\\", "/"))
    # Remove control characters, null bytes, and path traversal sequences
    cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)
    cleaned = re.sub(r'^\.+', '', cleaned)
    if not cleaned:
        cleaned = "attachment.bin"
    return cleaned

def normalize_domain(address: str) -> str:
    """Extract domain from an email address."""
    if "@" in address:
        domain = address.split("@")[-1].strip().lower()
        # Clean trailing brackets or punctuation
        domain = domain.rstrip(">.,; ")
        return domain or "unknown"
    return "unknown"

class MimeParser:
    """Parser for raw RFC822 / MIME messages."""

    def parse_bytes(self, raw_bytes: bytes, provider_message_id: Optional[str] = None) -> ParsedEmail:
        """Parse raw RFC822 message bytes into a structured ParsedEmail object."""
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        size_bytes = len(raw_bytes)
        
        try:
            msg = email.message_from_bytes(raw_bytes, policy=policy.default)
        except Exception:
            # Fallback for malformed bytes
            msg = email.message_from_bytes(raw_bytes, policy=policy.compat32)
            
        return self._extract_parsed_email(msg, raw_bytes, content_hash, size_bytes, provider_message_id)

    def _extract_parsed_email(
        self,
        msg: email.message.EmailMessage,
        raw_bytes: bytes,
        content_hash: str,
        size_bytes: int,
        provider_message_id: Optional[str]
    ) -> ParsedEmail:
        # Subject
        subject = str(msg.get("Subject", "")).strip() or "(No Subject)"
        
        # Message ID, References, In-Reply-To
        message_id_header = str(msg.get("Message-ID", "")).strip() or None
        in_reply_to = str(msg.get("In-Reply-To", "")).strip() or None
        references_header = str(msg.get("References", "")).strip() or None
        
        # Sender
        from_header = str(msg.get("From", ""))
        sender_name, sender_address = parseaddr(from_header)
        sender_address = sender_address.strip().lower() if sender_address else "unknown@unknown"
        sender_name = sender_name.strip()
        sender_domain = normalize_domain(sender_address)
        
        # Addresses list
        addresses: List[AddressInfo] = []
        if sender_address:
            addresses.append(AddressInfo(address=sender_address, display_name=sender_name, role="from"))
            
        for role, header_key in [("to", "To"), ("cc", "Cc"), ("bcc", "Bcc"), ("reply_to", "Reply-To")]:
            raw_val = msg.get(header_key)
            if raw_val:
                for name, addr in getaddresses([str(raw_val)]):
                    addr_clean = addr.strip().lower()
                    if addr_clean:
                        addresses.append(AddressInfo(address=addr_clean, display_name=name.strip(), role=role))
                        
        # Dates
        sent_at_str = None
        date_header = msg.get("Date")
        if date_header:
            try:
                dt = parsedate_to_datetime(str(date_header))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                sent_at_str = dt.isoformat()
            except Exception:
                sent_at_str = None
                
        received_at_str = sent_at_str or datetime.now(timezone.utc).isoformat()
        
        # Body and Attachments
        body_text_parts: List[str] = []
        body_html_parts: List[str] = []
        attachments: List[AttachmentInfo] = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                content_type = part.get_content_type()
                filename = part.get_filename()
                
                is_attachment = bool(filename) or "attachment" in content_disposition.lower()
                is_inline = "inline" in content_disposition.lower()
                
                if is_attachment:
                    safe_fn = sanitize_filename(filename)
                    payload = part.get_payload(decode=True)
                    att_size = len(payload) if payload else 0
                    att_hash = hashlib.sha256(payload).hexdigest() if payload else None
                    attachments.append(AttachmentInfo(
                        filename=safe_fn,
                        mime_type=content_type,
                        size_bytes=att_size,
                        content_hash=att_hash,
                        is_inline=is_inline,
                        content_available=bool(payload),
                        data=payload
                    ))
                else:
                    if content_type == "text/plain":
                        try:
                            payload = part.get_content()
                            if isinstance(payload, str):
                                body_text_parts.append(payload)
                        except Exception:
                            raw = part.get_payload(decode=True)
                            if raw:
                                body_text_parts.append(raw.decode("utf-8", errors="replace"))
                    elif content_type == "text/html":
                        try:
                            payload = part.get_content()
                            if isinstance(payload, str):
                                body_html_parts.append(payload)
                        except Exception:
                            raw = part.get_payload(decode=True)
                            if raw:
                                body_html_parts.append(raw.decode("utf-8", errors="replace"))
        else:
            content_type = msg.get_content_type()
            filename = msg.get_filename()
            if filename or "attachment" in str(msg.get("Content-Disposition", "")).lower():
                safe_fn = sanitize_filename(filename)
                payload = msg.get_payload(decode=True)
                att_size = len(payload) if payload else 0
                att_hash = hashlib.sha256(payload).hexdigest() if payload else None
                attachments.append(AttachmentInfo(
                    filename=safe_fn,
                    mime_type=content_type,
                    size_bytes=att_size,
                    content_hash=att_hash,
                    is_inline=False,
                    content_available=bool(payload),
                    data=payload
                ))
            elif content_type == "text/plain":
                try:
                    payload = msg.get_content()
                    if isinstance(payload, str):
                        body_text_parts.append(payload)
                except Exception:
                    raw = msg.get_payload(decode=True)
                    if raw:
                        body_text_parts.append(raw.decode("utf-8", errors="replace"))
            elif content_type == "text/html":
                try:
                    payload = msg.get_content()
                    if isinstance(payload, str):
                        body_html_parts.append(payload)
                except Exception:
                    raw = msg.get_payload(decode=True)
                    if raw:
                        body_html_parts.append(raw.decode("utf-8", errors="replace"))
                        
        body_text = "\n\n".join(body_text_parts).strip()
        body_html = "\n\n".join(body_html_parts).strip()
        
        # Snippet: first 250 characters of plain text
        snippet = re.sub(r'\s+', ' ', body_text)[:250].strip()
        if not snippet and body_html:
            # Strip tags for snippet
            clean_html = re.sub(r'<[^>]+>', ' ', body_html)
            snippet = re.sub(r'\s+', ' ', clean_html)[:250].strip()
            
        pid = provider_message_id or message_id_header or content_hash[:16]
        
        # Headers dict for classification rules
        headers_dict = {k.lower(): str(v) for k, v in msg.items()}
        
        return ParsedEmail(
            provider_message_id=pid,
            provider_thread_id=in_reply_to or message_id_header,
            message_id_header=message_id_header,
            in_reply_to=in_reply_to,
            references_header=references_header,
            subject=subject,
            sender_name=sender_name,
            sender_address=sender_address,
            sender_domain=sender_domain,
            sent_at=sent_at_str,
            received_at=received_at_str,
            is_read=False,
            is_starred=False,
            is_important=False,
            has_attachments=len(attachments) > 0,
            size_bytes=size_bytes,
            snippet=snippet,
            body_text=body_text,
            body_html=body_html,
            content_hash=content_hash,
            addresses=addresses,
            attachments=attachments,
            headers_dict=headers_dict
        )
