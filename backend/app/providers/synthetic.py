"""Synthetic mailbox generator for local testing, benchmarks, and demo mode."""

import random
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Generator, List, Optional
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.ingestion.mime_parser import ParsedEmail, AddressInfo, AttachmentInfo

DOMAINS = [
    ("acme-corp.com", "Acme Corporation"),
    ("github.com", "GitHub"),
    ("stripe.com", "Stripe"),
    ("amazon.com", "Amazon"),
    ("substack.com", "Substack Daily"),
    ("accounts.google.com", "Google Accounts"),
    ("uber.com", "Uber Receipts"),
    ("apple.com", "Apple"),
    ("mit.edu", "MIT Academic"),
    ("netflix.com", "Netflix"),
    ("figma.com", "Figma Design"),
    ("digitalocean.com", "DigitalOcean Cloud")
]

SENDERS_SPEC = [
    # domain, username, display_name, category_hint
    ("acme-corp.com", "sarah.connor", "Sarah Connor", "work"),
    ("acme-corp.com", "david.kim", "David Kim (Lead Architect)", "work"),
    ("acme-corp.com", "hr-updates", "Acme People Ops", "notification"),
    ("github.com", "notifications", "GitHub Notifications", "notification"),
    ("stripe.com", "invoices", "Stripe Invoicing", "receipt_invoice"),
    ("amazon.com", "auto-confirm", "Amazon.com Orders", "transactional"),
    ("substack.com", "techdigest", "Pragmatic Engineer Digest", "newsletter"),
    ("substack.com", "systemdesign", "ByteByteGo Newsletter", "newsletter"),
    ("accounts.google.com", "no-reply", "Google Security Alerts", "security"),
    ("uber.com", "receipts", "Uber Receipts", "receipt_invoice"),
    ("apple.com", "no_reply", "Apple Services", "receipt_invoice"),
    ("mit.edu", "advising", "MIT Academic Office", "university"),
    ("netflix.com", "info", "Netflix Recommendations", "promotional"),
    ("figma.com", "comments", "Figma Design Comments", "notification"),
    ("digitalocean.com", "billing", "DigitalOcean Billing", "receipt_invoice")
]

ATTACHMENT_TEMPLATES = [
    ("Q3_Financial_Summary.pdf", "application/pdf", 1450200),
    ("architecture_diagram_v2.png", "image/png", 523100),
    ("invoice_INV_9821.pdf", "application/pdf", 89400),
    ("project_specs.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 340100),
    ("database_dump_test.sql.gz", "application/gzip", 4210000),
    ("meeting_notes_october.pdf", "application/pdf", 112000),
    ("receipt_20261011.pdf", "application/pdf", 76300)
]

class SyntheticMailboxGenerator(AbstractMailProvider):
    """Generates deterministic synthetic email data for testing and offline evaluation."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_archive=True,
            supports_trash=True,
            supports_undo=True,
            supports_labels=True,
            is_read_only=False,
            provider_name="synthetic"
        )

    def connect(self) -> bool:
        return True

    def list_folders(self) -> List[ProviderFolder]:
        return [
            ProviderFolder(id="inbox", name="INBOX", folder_type="inbox", is_special=True),
            ProviderFolder(id="archive", name="Archive", folder_type="archive", is_special=True),
            ProviderFolder(id="trash", name="Trash", folder_type="trash", is_special=True),
            ProviderFolder(id="sent", name="Sent", folder_type="sent", is_special=True),
        ]

    def stream_messages(self, folder_id: Optional[str] = None, limit: Optional[int] = None) -> Generator[ParsedEmail, None, None]:
        count = limit or 100
        yield from self.generate(count=count)

    def generate(self, count: int = 100) -> Generator[ParsedEmail, None, None]:
        """Generate a specified number of synthetic emails."""
        base_date = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Track threads for realistic reply chains
        threads: List[dict] = []
        
        for i in range(count):
            sender_info = self.rng.choice(SENDERS_SPEC)
            domain, user, display_name, cat = sender_info
            sender_address = f"{user}@{domain}"
            
            # Message timestamp
            days_ago = self.rng.randint(0, 365)
            hours_ago = self.rng.randint(0, 23)
            mins_ago = self.rng.randint(0, 59)
            msg_date = base_date - timedelta(days=days_ago, hours=hours_ago, minutes=mins_ago)
            date_str = msg_date.isoformat()
            
            # Unique message identifier
            provider_id = f"synth_{self.seed}_{i:05d}"
            msg_id_header = f"<{provider_id}@{domain}>"
            
            # Determine if this message is part of an existing thread (35% probability if threads exist)
            in_reply_to = None
            references_header = None
            if threads and self.rng.random() < 0.35:
                parent_thread = self.rng.choice(threads)
                subject = f"Re: {parent_thread['subject']}"
                in_reply_to = parent_thread['last_msg_id']
                references_header = f"{parent_thread.get('references', '')} {in_reply_to}".strip()
                provider_thread_id = parent_thread['thread_id']
                # Update thread
                parent_thread['last_msg_id'] = msg_id_header
                parent_thread['references'] = references_header
            else:
                subjects = [
                    f"Sprint Planning & Roadmap Review for Q{self.rng.randint(1,4)}",
                    f"Your Invoice for Order #{self.rng.randint(10000, 99999)}",
                    f"Security Alert: New Sign-in from Chrome on Windows",
                    f"Weekly Tech Digest: Issue #{self.rng.randint(100, 350)}",
                    f"Flight confirmation and check-in details",
                    f"Critical bug report in production cluster",
                    f"Design system tokens update and preview link",
                    f"Monthly account statement and billing details",
                    f"Coffee chat or 1:1 catch-up next week?",
                    f"Invitation: Quarterly all-hands engineering sync"
                ]
                subject = self.rng.choice(subjects)
                provider_thread_id = f"thread_{self.seed}_{i:05d}"
                threads.append({
                    'thread_id': provider_thread_id,
                    'subject': subject,
                    'last_msg_id': msg_id_header,
                    'references': msg_id_header
                })
                
            # Content snippet & body
            body_text = (
                f"Hello,\n\nThis is an automated synthetic message simulating realistic email contents "
                f"for subject '{subject}'.\n\n"
                f"Reference details:\n- Department: {domain}\n- Tracking ID: {provider_id}\n\n"
                f"Best regards,\n{display_name}"
            )
            snippet = body_text.replace("\n", " ")[:200]
            
            # Attachments (25% probability)
            attachments: List[AttachmentInfo] = []
            has_attachments = False
            if self.rng.random() < 0.25:
                has_attachments = True
                fn, mime, size = self.rng.choice(ATTACHMENT_TEMPLATES)
                att_hash = hashlib.sha256(f"{fn}_{size}_{self.seed}".encode("utf-8")).hexdigest()
                attachments.append(AttachmentInfo(
                    filename=fn,
                    mime_type=mime,
                    size_bytes=size,
                    content_hash=att_hash,
                    is_inline=False,
                    content_available=True,
                    data=b"SYNTHETIC_ATTACHMENT_BYTES"
                ))
                
            raw_content = f"{msg_id_header}\n{subject}\n{body_text}".encode("utf-8")
            content_hash = hashlib.sha256(raw_content).hexdigest()
            size_bytes = len(raw_content) + sum(a.size_bytes for a in attachments)
            
            is_read = self.rng.random() < 0.65
            is_starred = self.rng.random() < 0.10
            is_important = self.rng.random() < 0.15
            
            # Addresses
            addresses = [
                AddressInfo(address=sender_address, display_name=display_name, role="from"),
                AddressInfo(address="me@local.mailbox", display_name="Me", role="to")
            ]
            if self.rng.random() < 0.20:
                addresses.append(AddressInfo(address="colleague@acme-corp.com", display_name="Colleague", role="cc"))
                
            # Headers dict
            headers_dict = {
                "from": f'"{display_name}" <{sender_address}>',
                "to": "me@local.mailbox",
                "subject": subject,
                "date": date_str,
                "message-id": msg_id_header
            }
            if "newsletter" in sender_address or "substack" in domain:
                headers_dict["list-unsubscribe"] = f"<mailto:unsub@{domain}>, <https://{domain}/unsub>"
                headers_dict["precedence"] = "bulk"
                
            yield ParsedEmail(
                provider_message_id=provider_id,
                provider_thread_id=provider_thread_id,
                message_id_header=msg_id_header,
                in_reply_to=in_reply_to,
                references_header=references_header,
                subject=subject,
                sender_name=display_name,
                sender_address=sender_address,
                sender_domain=domain,
                sent_at=date_str,
                received_at=date_str,
                is_read=is_read,
                is_starred=is_starred,
                is_important=is_important,
                has_attachments=has_attachments,
                size_bytes=size_bytes,
                snippet=snippet,
                body_text=body_text,
                body_html=f"<div><p>{body_text.replace(chr(10), '<br>')}</p></div>",
                content_hash=content_hash,
                addresses=addresses,
                attachments=attachments,
                headers_dict=headers_dict
            )
