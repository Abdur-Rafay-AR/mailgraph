"""HTML email sanitizer protecting against XSS, remote tracking, and malicious embeds."""

import re
import bleach

ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div',
    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'li', 'ol',
    'p', 'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead',
    'tr', 'ul', 'img'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
    '*': ['style', 'class', 'align', 'valign']
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

class HtmlSanitizer:
    """Sanitizes raw HTML emails for safe rendering inside the desktop viewer."""

    @staticmethod
    def sanitize(raw_html: str, allow_remote_images: bool = False) -> str:
        """Strip dangerous tags, scripts, and neutralize remote tracker images if blocked."""
        if not raw_html:
            return ""
            
        # Clean with bleach
        cleaned = bleach.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True
        )
        
        # Block remote images if disabled by default
        if not allow_remote_images:
            # Replace http/https img src with a placeholder data attribute
            cleaned = re.sub(
                r'<img\s+([^>]*?)src=["\'](https?://[^"\']+)["\']([^>]*)>',
                r'<span class="remote-image-blocked" data-src="\2" title="Remote image blocked for privacy">[Image Blocked]</span>',
                cleaned,
                flags=re.IGNORECASE
            )
            
        return cleaned
