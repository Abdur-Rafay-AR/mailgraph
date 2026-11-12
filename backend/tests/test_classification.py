import pytest
from backend.app.ingestion.mime_parser import ParsedEmail
from backend.app.classification.rules_engine import RulesEngine

def test_classify_newsletter_by_headers():
    engine = RulesEngine()
    email_msg = ParsedEmail(
        provider_message_id="news_1",
        subject="The Pragmatic Engineer: Architecture Patterns",
        sender_address="newsletter@pragmaticengineer.com",
        sender_domain="pragmaticengineer.com",
        headers_dict={
            "list-unsubscribe": "<mailto:unsub@pragmaticengineer.com>",
            "precedence": "bulk"
        }
    )
    cat, confidence, reason = engine.classify(email_msg)
    assert cat == "newsletter"
    assert confidence >= 0.9
    assert "List-Unsubscribe" in reason

def test_classify_security_alert():
    engine = RulesEngine()
    email_msg = ParsedEmail(
        provider_message_id="sec_1",
        subject="Security alert: New login from Firefox on Linux",
        sender_address="no-reply@accounts.google.com",
        sender_domain="accounts.google.com"
    )
    cat, confidence, reason = engine.classify(email_msg)
    assert cat == "security"
    assert confidence >= 0.85

def test_classify_receipt_invoice():
    engine = RulesEngine()
    email_msg = ParsedEmail(
        provider_message_id="rcpt_1",
        subject="Your Stripe Invoice #10492 for October 2026",
        sender_address="invoices@stripe.com",
        sender_domain="stripe.com"
    )
    cat, confidence, reason = engine.classify(email_msg)
    assert cat == "receipt_invoice"
    assert confidence >= 0.85

def test_classify_university():
    engine = RulesEngine()
    email_msg = ParsedEmail(
        provider_message_id="edu_1",
        subject="Course Registration Reminder for Spring Semester",
        sender_address="registrar@stanford.edu",
        sender_domain="stanford.edu"
    )
    cat, confidence, reason = engine.classify(email_msg)
    assert cat == "university"

def test_classify_calendar():
    engine = RulesEngine()
    email_msg = ParsedEmail(
        provider_message_id="cal_1",
        subject="Invitation: Design Sprint Kickoff @ Thu Oct 15",
        sender_address="organizer@company.com",
        sender_domain="company.com"
    )
    cat, confidence, reason = engine.classify(email_msg)
    assert cat == "calendar"
