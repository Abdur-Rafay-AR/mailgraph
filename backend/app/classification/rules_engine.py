"""Deterministic heuristic classification engine for email categorization."""

import re
from typing import Tuple, Optional
from backend.app.ingestion.mime_parser import ParsedEmail

SECURITY_PATTERNS = re.compile(
    r"(security alert|password reset|two-factor|2fa|verify your (email|identity|account)|verification code|"
    r"suspicious (login|activity)|unauthorized access|new sign-in|passcode)",
    re.IGNORECASE
)

RECEIPT_PATTERNS = re.compile(
    r"(invoice|receipt|order confirmation|payment received|billing statement|your order of|subscription renewed|"
    r"payment confirmation|tax invoice|shipped:|delivery confirmation)",
    re.IGNORECASE
)

CALENDAR_PATTERNS = re.compile(
    r"(invitation:|accepted:|declined:|updated invitation:|tentative:|event cancelled:|calendar reminder)",
    re.IGNORECASE
)

NEWSLETTER_PATTERNS = re.compile(
    r"(newsletter|weekly digest|daily digest|dispatch|roundup|edition #|issue #|the pragmatic engineer|bytebytego|tldr)",
    re.IGNORECASE
)

PROMOTIONAL_PATTERNS = re.compile(
    r"(% off|discount|black friday|cyber monday|exclusive deal|flash sale|promo code|special offer|ends tonight|clearance)",
    re.IGNORECASE
)

SOCIAL_PATTERNS = re.compile(
    r"(tagged you|mentioned you|new connection|liked your|started following you|shared a post|in your network)",
    re.IGNORECASE
)

REPORT_PATTERNS = re.compile(
    r"(build succeeded|build failed|pipeline (failed|passed)|cron job|status report|daily metrics|incident alert)",
    re.IGNORECASE
)

class RulesEngine:
    """Classifies emails into explainable categories based on deterministic signals."""

    def classify(self, email_msg: ParsedEmail) -> Tuple[str, float, str]:
        """
        Evaluate headers, sender, and subject to determine the appropriate category.
        Returns: (category_name, confidence, explainable_reason)
        """
        headers = email_msg.headers_dict or {}
        subject = email_msg.subject or ""
        sender_addr = (email_msg.sender_address or "").lower()
        domain = (email_msg.sender_domain or "").lower()
        
        # 1. Security Alert Check (Highest priority for protection)
        if SECURITY_PATTERNS.search(subject) or "security" in sender_addr or "accounts.google.com" in domain:
            return "security", 0.95, "Matches security verification, password reset, or authentication pattern"
            
        # 2. Calendar Event Check
        if CALENDAR_PATTERNS.search(subject) or "calendar" in headers.get("content-type", "").lower():
            return "calendar", 0.90, "Contains calendar invitation or RSVP indicators"
            
        # 3. Receipt / Invoices
        if RECEIPT_PATTERNS.search(subject) or "receipt" in sender_addr or "invoice" in sender_addr or "billing" in sender_addr:
            return "receipt_invoice", 0.92, "Subject or sender contains billing, receipt, or invoice indicators"
            
        # 4. Newsletters
        if "list-unsubscribe" in headers or headers.get("precedence") == "bulk" or NEWSLETTER_PATTERNS.search(subject) or "substack" in domain:
            reason = "Contains List-Unsubscribe header" if "list-unsubscribe" in headers else "Matches recurring newsletter publication pattern"
            conf = 0.95 if "list-unsubscribe" in headers else 0.88
            return "newsletter", conf, reason
            
        # 5. University / Academic
        if domain.endswith(".edu") or domain.endswith(".ac.uk"):
            return "university", 0.95, f"Sender domain ends with academic TLD (.{domain.split('.')[-1]})"
            
        # 6. Automated Reports / CI
        if REPORT_PATTERNS.search(subject) or "noreply" in sender_addr or "no-reply" in sender_addr and "cron" in subject.lower():
            return "automated_report", 0.85, "Matches automated CI/CD build or system status report pattern"
            
        # 7. Promotional / Sales
        if PROMOTIONAL_PATTERNS.search(subject):
            return "promotional", 0.85, "Subject contains commercial promotion or discount indicators"
            
        # 8. Social Network
        if SOCIAL_PATTERNS.search(subject) or any(s in domain for s in ["linkedin.com", "twitter.com", "x.com", "instagram.com", "facebookmail.com"]):
            return "social", 0.90, "Originates from a recognized social network platform"
            
        # 9. Generic Notification
        if "notification" in sender_addr or "alert" in sender_addr or "system" in sender_addr or "no-reply" in sender_addr or "noreply" in sender_addr:
            return "notification", 0.80, "Sender address is designated for non-reply automated notifications"
            
        # 10. Personal / Work / Unknown
        if email_msg.in_reply_to or (email_msg.subject.lower().startswith("re:") and len(email_msg.addresses) <= 3):
            return "personal", 0.75, "Direct conversational reply chain with few participants"
            
        return "unknown", 0.50, "No strong heuristic rules matched"
