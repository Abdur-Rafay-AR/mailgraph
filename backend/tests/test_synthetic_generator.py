import pytest
from backend.app.providers.synthetic import SyntheticMailboxGenerator

def test_synthetic_generator_creates_valid_messages():
    generator = SyntheticMailboxGenerator(seed=42)
    messages = list(generator.generate(count=50))
    
    assert len(messages) == 50
    
    senders = {m.sender_address for m in messages}
    domains = {m.sender_domain for m in messages}
    assert len(senders) >= 10
    assert len(domains) >= 5
    
    # Check that some messages have attachments and some have thread replies
    with_attachments = [m for m in messages if m.has_attachments]
    with_replies = [m for m in messages if m.in_reply_to is not None]
    
    assert len(with_attachments) > 0
    assert len(with_replies) > 0

def test_synthetic_generator_deterministic_output():
    gen1 = SyntheticMailboxGenerator(seed=12345)
    gen2 = SyntheticMailboxGenerator(seed=12345)
    
    m1 = list(gen1.generate(count=10))
    m2 = list(gen2.generate(count=10))
    
    for a, b in zip(m1, m2):
        assert a.subject == b.subject
        assert a.sender_address == b.sender_address
        assert a.sent_at == b.sent_at
