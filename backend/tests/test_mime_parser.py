import pytest
from datetime import datetime
from backend.app.ingestion.mime_parser import MimeParser

SAMPLE_RAW_EMAIL = """From: "Jane Doe" <jane.doe@example.com>
To: John Smith <john.smith@company.org>, dev-team@company.org
Cc: manager@company.org
Subject: Quarterly Roadmap Discussion & Review
Date: Thu, 12 Oct 2026 14:32:00 +0000
Message-ID: <msg-101@example.com>
References: <msg-099@example.com> <msg-100@example.com>
In-Reply-To: <msg-100@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY123"

--BOUNDARY123
Content-Type: text/plain; charset="utf-8"

Hi team,

Here is the updated roadmap document. Please review the attached spreadsheet before our 3 PM meeting.

Thanks,
Jane

--BOUNDARY123
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="roadmap_q4.xlsx"
Content-Transfer-Encoding: base64

UEsDBBQAAAAIAAAAAAAAAAAAAAAAAAAAAAA=
--BOUNDARY123--
"""

def test_mime_parser_extracts_headers():
    parser = MimeParser()
    parsed = parser.parse_bytes(SAMPLE_RAW_EMAIL.encode("utf-8"))
    
    assert parsed.sender_name == "Jane Doe"
    assert parsed.sender_address == "jane.doe@example.com"
    assert parsed.sender_domain == "example.com"
    assert parsed.subject == "Quarterly Roadmap Discussion & Review"
    assert parsed.message_id_header == "<msg-101@example.com>"
    assert parsed.in_reply_to == "<msg-100@example.com>"
    assert "<msg-099@example.com>" in parsed.references_header
    assert parsed.sent_at is not None
    assert parsed.sent_at.startswith("2026-10-12")

def test_mime_parser_extracts_recipients():
    parser = MimeParser()
    parsed = parser.parse_bytes(SAMPLE_RAW_EMAIL.encode("utf-8"))
    
    to_addrs = [a.address for a in parsed.addresses if a.role == "to"]
    cc_addrs = [a.address for a in parsed.addresses if a.role == "cc"]
    
    assert "john.smith@company.org" in to_addrs
    assert "dev-team@company.org" in to_addrs
    assert "manager@company.org" in cc_addrs

def test_mime_parser_extracts_attachments_safely():
    parser = MimeParser()
    parsed = parser.parse_bytes(SAMPLE_RAW_EMAIL.encode("utf-8"))
    
    assert len(parsed.attachments) == 1
    att = parsed.attachments[0]
    assert att.filename == "roadmap_q4.xlsx"
    assert "spreadsheet" in att.mime_type
    assert not att.is_inline

def test_mime_parser_sanitizes_attachment_filenames():
    raw_traversal = """From: attacker@evil.com
To: victim@example.com
Subject: Malicious Attachment Test
Date: Wed, 11 Oct 2026 10:00:00 +0000
Message-ID: <evil-1@evil.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="EVIL"

--EVIL
Content-Type: text/plain
Content-Disposition: attachment; filename="../../windows/system32/cmd.exe"

test
--EVIL--
"""
    parser = MimeParser()
    parsed = parser.parse_bytes(raw_traversal.encode("utf-8"))
    assert len(parsed.attachments) == 1
    # Path traversal should be stripped
    assert ".." not in parsed.attachments[0].filename
    assert "/" not in parsed.attachments[0].filename
    assert "\\" not in parsed.attachments[0].filename
    assert parsed.attachments[0].filename == "cmd.exe"

def test_mime_parser_handles_malformed_email():
    malformed = b"This is not a valid email message with headers\n\nJust some random data"
    parser = MimeParser()
    parsed = parser.parse_bytes(malformed)
    assert parsed is not None
    assert parsed.sender_address == "unknown@unknown"
