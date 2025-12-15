"""Classification result models."""

from dataclasses import dataclass, field
from enum import Enum


class JunkIndicator(Enum):
    """Types of junk indicators found in emails."""

    SUSPICIOUS_SENDER = "suspicious_sender"
    SPAM_KEYWORDS = "spam_keywords"
    PHISHING_PATTERNS = "phishing_patterns"
    SUSPICIOUS_LINKS = "suspicious_links"
    PROMOTIONAL_CONTENT = "promotional_content"
    UNSUBSCRIBE_LINK = "unsubscribe_link"
    BULK_MAIL_HEADER = "bulk_mail_header"
    LOW_REPUTATION_DOMAIN = "low_reputation_domain"
    MISSING_AUTHENTICATION = "missing_authentication"
    URGENCY_LANGUAGE = "urgency_language"
    MONEY_SCAM_PATTERNS = "money_scam_patterns"
    LOTTERY_SCAM = "lottery_scam"
    NEWSLETTER = "newsletter"
    MARKETING_EMAIL = "marketing_email"


@dataclass
class JunkClassification:
    """Result of junk email classification."""

    email_uid: int
    is_junk: bool
    confidence: float
    indicators: list[JunkIndicator] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = "none"

    def add_indicator(self, indicator: JunkIndicator, reason: str, weight: float = 0.1):
        """Add a junk indicator with its reason."""
        if indicator not in self.indicators:
            self.indicators.append(indicator)
            self.reasons.append(reason)
            self.confidence = min(1.0, self.confidence + weight)

    def __str__(self) -> str:
        status = "JUNK" if self.is_junk else "CLEAN"
        return f"Classification(uid={self.email_uid}, {status}, confidence={self.confidence:.2f})"
