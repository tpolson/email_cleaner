"""Email data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EmailHeader:
    """Email header information."""

    name: str
    value: str


@dataclass
class Email:
    """Represents an email message."""

    uid: int
    message_id: str
    sender: str
    sender_name: str
    recipients: list[str]
    subject: str
    body_text: str
    body_html: str
    received_date: datetime
    headers: list[EmailHeader] = field(default_factory=list)
    has_attachments: bool = False
    folder: str = "INBOX"

    @property
    def sender_domain(self) -> str:
        """Extract domain from sender email."""
        if "@" in self.sender:
            return self.sender.split("@")[-1].lower()
        return ""

    def get_header(self, name: str) -> Optional[str]:
        """Get a specific header value by name."""
        for header in self.headers:
            if header.name.lower() == name.lower():
                return header.value
        return None

    def __str__(self) -> str:
        return f"Email(uid={self.uid}, from={self.sender}, subject={self.subject[:50]}...)"
