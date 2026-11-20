"""HTML email sanitizer protecting against XSS, remote tracking, and malicious embeds."""

import html
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
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*': ['class', 'align', 'valign']
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

_DANGEROUS_BLOCKS_RE = re.compile(
    r'<\s*(script|style|iframe|object|embed|noscript|svg)[^>]*>.*?<\s*/\s*\1\s*>',
    re.IGNORECASE | re.DOTALL
)
_REMOTE_IMG_RE = re.compile(
    r'<img\s+([^>]*?)src=["\'](https?://[^"\']+)["\']([^>]*)>',
    re.IGNORECASE
)
_LINK_TAG_RE = re.compile(r'<a\b([^>]*)>', re.IGNORECASE)


class HtmlSanitizer:
    """Sanitizes raw HTML emails for safe rendering inside the desktop viewer."""

    @staticmethod
    def sanitize(raw_html: str, allow_remote_images: bool = False) -> str:
        """Strip dangerous tags, scripts, and neutralize remote tracker images if blocked."""
        if not raw_html:
            return ""

        # Strip entire dangerous tag blocks including their inner text before bleach runs
        stripped = _DANGEROUS_BLOCKS_RE.sub("", raw_html)

        cleaned = bleach.clean(
            stripped,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True
        )

        # Enforce safe external link attributes
        def _harden_link(match: re.Match) -> str:
            attrs = match.group(1)
            if "rel=" not in attrs.lower():
                attrs += ' rel="noopener noreferrer"'
            if "target=" not in attrs.lower():
                attrs += ' target="_blank"'
            return f"<a{attrs}>"

        cleaned = _LINK_TAG_RE.sub(_harden_link, cleaned)

        # Block remote images if disabled
        if not allow_remote_images:
            cleaned = _REMOTE_IMG_RE.sub(
                r'<span class="remote-image-blocked" data-src="\2" title="Remote image blocked for privacy">[Image Blocked]</span>',
                cleaned
            )

        return cleaned

    @staticmethod
    def render_plain_text_preview(body_text: str) -> str:
        """Safely HTML-escape plain text email content for preview rendering."""
        if not body_text:
            return ""
        escaped = html.escape(body_text, quote=True)
        return (
            '<div style="font-family: inherit; white-space: pre-wrap; line-height: 1.6;">'
            f"{escaped}"
            "</div>"
        )
