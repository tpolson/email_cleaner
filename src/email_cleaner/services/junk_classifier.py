"""Junk email classifier service."""

import re
from ..models import Email, JunkClassification, JunkIndicator


class JunkClassifier:
    """Classifier for detecting junk/spam emails."""

    # Spam keywords commonly found in junk emails
    SPAM_KEYWORDS = [
        "viagra", "cialis", "pharmacy", "pills", "medication",
        "casino", "lottery", "winner", "jackpot", "prize",
        "nigerian prince", "inheritance", "beneficiary",
        "wire transfer", "western union", "moneygram",
        "click here", "click now", "act now", "limited time",
        "free gift", "free money", "free offer",
        "make money fast", "work from home", "earn extra cash",
        "weight loss", "lose weight", "diet pill",
        "credit card", "debt relief", "loan approved",
        "refinance", "mortgage rate",
    ]

    # Phishing indicators
    PHISHING_PATTERNS = [
        r"verify your account",
        r"confirm your identity",
        r"update your payment",
        r"suspicious activity",
        r"account suspended",
        r"account locked",
        r"password expired",
        r"security alert",
        r"unusual sign-?in",
        r"action required",
    ]

    # Urgency language patterns
    URGENCY_PATTERNS = [
        r"urgent",
        r"immediate(ly)?",
        r"act now",
        r"don't delay",
        r"expires? (today|soon|in \d+)",
        r"last chance",
        r"final notice",
        r"time sensitive",
        r"limited time",
        r"only \d+ (left|remaining|available)",
    ]

    # Money scam patterns
    MONEY_SCAM_PATTERNS = [
        r"\$[\d,]+(?:\.\d{2})?\s*(million|billion|usd|dollars)",
        r"(million|billion)\s*dollars",
        r"bank transfer",
        r"wire\s*(the )?(money|funds|amount)",
        r"send (money|funds|payment)",
        r"processing fee",
        r"advance fee",
        r"claim (your |the )?(money|funds|prize|inheritance)",
    ]

    # Known suspicious TLDs
    SUSPICIOUS_TLDS = [
        ".xyz", ".top", ".win", ".loan", ".click", ".link",
        ".gdn", ".racing", ".review", ".country", ".stream",
        ".download", ".accountant", ".science", ".work",
    ]

    # Promotional/newsletter indicators
    PROMOTIONAL_PATTERNS = [
        r"unsubscribe",
        r"opt[ -]?out",
        r"email preferences",
        r"manage (your )?subscriptions?",
        r"view (this )?(email )?in (your )?browser",
        r"add us to your (address book|contacts)",
        r"(special|exclusive) offer",
        r"% off",
        r"sale ends",
        r"shop now",
        r"buy now",
        r"order now",
        r"free shipping",
    ]

    def __init__(self, confidence_threshold: float = 0.7):
        """Initialize the classifier.

        Args:
            confidence_threshold: Minimum confidence to classify as junk
        """
        self.confidence_threshold = confidence_threshold

    def classify(self, email: Email) -> JunkClassification:
        """Classify an email as junk or not.

        Args:
            email: Email to classify

        Returns:
            JunkClassification result
        """
        result = JunkClassification(
            email_uid=email.uid,
            is_junk=False,
            confidence=0.0,
        )

        # Combine text for analysis
        full_text = f"{email.subject} {email.body_text} {email.body_html}".lower()

        # Run all checks
        self._check_spam_keywords(email, full_text, result)
        self._check_phishing_patterns(email, full_text, result)
        self._check_urgency_language(full_text, result)
        self._check_money_scams(full_text, result)
        self._check_suspicious_sender(email, result)
        self._check_suspicious_links(email, result)
        self._check_promotional_content(email, full_text, result)
        self._check_bulk_mail_headers(email, result)
        self._check_authentication_headers(email, result)

        # Determine final classification
        result.is_junk = result.confidence >= self.confidence_threshold

        # Set recommended action
        if result.is_junk:
            if result.confidence >= 0.9:
                result.recommended_action = "delete"
            elif result.confidence >= 0.8:
                result.recommended_action = "move_to_spam"
            else:
                result.recommended_action = "review"
        else:
            result.recommended_action = "keep"

        return result

    def _check_spam_keywords(
        self, email: Email, text: str, result: JunkClassification
    ) -> None:
        """Check for common spam keywords."""
        found_keywords = []
        for keyword in self.SPAM_KEYWORDS:
            if keyword.lower() in text:
                found_keywords.append(keyword)

        if found_keywords:
            result.add_indicator(
                JunkIndicator.SPAM_KEYWORDS,
                f"Contains spam keywords: {', '.join(found_keywords[:5])}",
                weight=min(0.3, len(found_keywords) * 0.1),
            )

    def _check_phishing_patterns(
        self, email: Email, text: str, result: JunkClassification
    ) -> None:
        """Check for phishing patterns."""
        found_patterns = []
        for pattern in self.PHISHING_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(pattern)

        if found_patterns:
            result.add_indicator(
                JunkIndicator.PHISHING_PATTERNS,
                f"Contains phishing patterns: {len(found_patterns)} found",
                weight=0.4,
            )

    def _check_urgency_language(
        self, text: str, result: JunkClassification
    ) -> None:
        """Check for urgency language."""
        urgency_count = 0
        for pattern in self.URGENCY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                urgency_count += 1

        if urgency_count >= 2:
            result.add_indicator(
                JunkIndicator.URGENCY_LANGUAGE,
                f"Contains excessive urgency language: {urgency_count} patterns",
                weight=0.2,
            )

    def _check_money_scams(
        self, text: str, result: JunkClassification
    ) -> None:
        """Check for money scam patterns."""
        for pattern in self.MONEY_SCAM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                result.add_indicator(
                    JunkIndicator.MONEY_SCAM_PATTERNS,
                    "Contains money scam language patterns",
                    weight=0.35,
                )
                break

        # Check for lottery scam
        lottery_patterns = [
            r"you('ve| have)? (been selected|won)",
            r"congratulations.{0,20}(winner|won|prize)",
            r"lottery.{0,20}(winner|won|claim)",
        ]
        for pattern in lottery_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result.add_indicator(
                    JunkIndicator.LOTTERY_SCAM,
                    "Appears to be a lottery/prize scam",
                    weight=0.4,
                )
                break

    def _check_suspicious_sender(
        self, email: Email, result: JunkClassification
    ) -> None:
        """Check for suspicious sender characteristics."""
        sender_domain = email.sender_domain

        # Check for suspicious TLDs
        for tld in self.SUSPICIOUS_TLDS:
            if sender_domain.endswith(tld):
                result.add_indicator(
                    JunkIndicator.LOW_REPUTATION_DOMAIN,
                    f"Sender uses suspicious TLD: {tld}",
                    weight=0.25,
                )
                break

        # Check for random-looking sender
        if self._looks_random(sender_domain.split(".")[0]):
            result.add_indicator(
                JunkIndicator.SUSPICIOUS_SENDER,
                "Sender domain appears randomly generated",
                weight=0.2,
            )

        # Check for display name / email mismatch (common in phishing)
        if email.sender_name:
            # If sender name looks like an email but doesn't match actual email
            if "@" in email.sender_name:
                name_domain = email.sender_name.split("@")[-1].lower()
                if name_domain != sender_domain:
                    result.add_indicator(
                        JunkIndicator.SUSPICIOUS_SENDER,
                        "Display name email doesn't match actual sender",
                        weight=0.3,
                    )

    def _check_suspicious_links(
        self, email: Email, result: JunkClassification
    ) -> None:
        """Check for suspicious links in the email."""
        # Find all URLs in HTML
        url_pattern = r'href=["\']?(https?://[^"\'\s>]+)'
        urls = re.findall(url_pattern, email.body_html, re.IGNORECASE)

        suspicious_urls = []
        for url in urls:
            # Check for IP addresses instead of domains
            if re.search(r"https?://\d+\.\d+\.\d+\.\d+", url):
                suspicious_urls.append("IP-based URL")

            # Check for suspicious TLDs
            for tld in self.SUSPICIOUS_TLDS:
                if tld in url.lower():
                    suspicious_urls.append(f"Suspicious TLD ({tld})")
                    break

            # Check for URL shorteners
            shorteners = ["bit.ly", "tinyurl", "goo.gl", "t.co", "ow.ly", "is.gd"]
            for shortener in shorteners:
                if shortener in url.lower():
                    suspicious_urls.append("URL shortener")
                    break

        if suspicious_urls:
            result.add_indicator(
                JunkIndicator.SUSPICIOUS_LINKS,
                f"Contains suspicious links: {', '.join(set(suspicious_urls[:3]))}",
                weight=0.25,
            )

    def _check_promotional_content(
        self, email: Email, text: str, result: JunkClassification
    ) -> None:
        """Check for promotional/newsletter content."""
        promo_count = 0
        has_unsubscribe = False

        for pattern in self.PROMOTIONAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                promo_count += 1
                if "unsubscribe" in pattern or "opt" in pattern:
                    has_unsubscribe = True

        if has_unsubscribe:
            result.add_indicator(
                JunkIndicator.UNSUBSCRIBE_LINK,
                "Contains unsubscribe link (likely newsletter/marketing)",
                weight=0.1,
            )

        if promo_count >= 3:
            result.add_indicator(
                JunkIndicator.PROMOTIONAL_CONTENT,
                f"Contains promotional language: {promo_count} indicators",
                weight=0.15,
            )

    def _check_bulk_mail_headers(
        self, email: Email, result: JunkClassification
    ) -> None:
        """Check email headers for bulk mail indicators."""
        # Check for precedence header
        precedence = email.get_header("Precedence")
        if precedence and precedence.lower() in ["bulk", "junk", "list"]:
            result.add_indicator(
                JunkIndicator.BULK_MAIL_HEADER,
                f"Precedence header indicates bulk mail: {precedence}",
                weight=0.15,
            )

        # Check for List-Unsubscribe header
        list_unsub = email.get_header("List-Unsubscribe")
        if list_unsub:
            result.add_indicator(
                JunkIndicator.NEWSLETTER,
                "Has List-Unsubscribe header (mailing list/newsletter)",
                weight=0.1,
            )

        # Check for X-Mailer indicating bulk sending
        x_mailer = email.get_header("X-Mailer")
        if x_mailer:
            bulk_mailers = ["mailchimp", "sendgrid", "mailgun", "constant contact", "campaign monitor"]
            if any(mailer in x_mailer.lower() for mailer in bulk_mailers):
                result.add_indicator(
                    JunkIndicator.MARKETING_EMAIL,
                    f"Sent via marketing platform: {x_mailer}",
                    weight=0.1,
                )

    def _check_authentication_headers(
        self, email: Email, result: JunkClassification
    ) -> None:
        """Check email authentication headers (SPF, DKIM, DMARC)."""
        auth_results = email.get_header("Authentication-Results")
        received_spf = email.get_header("Received-SPF")

        failed_auth = []

        if auth_results:
            auth_lower = auth_results.lower()
            if "spf=fail" in auth_lower or "spf=softfail" in auth_lower:
                failed_auth.append("SPF")
            if "dkim=fail" in auth_lower:
                failed_auth.append("DKIM")
            if "dmarc=fail" in auth_lower:
                failed_auth.append("DMARC")

        if received_spf:
            spf_lower = received_spf.lower()
            if "fail" in spf_lower and "SPF" not in failed_auth:
                failed_auth.append("SPF")

        if failed_auth:
            result.add_indicator(
                JunkIndicator.MISSING_AUTHENTICATION,
                f"Email authentication failures: {', '.join(failed_auth)}",
                weight=0.3,
            )

    def _looks_random(self, text: str) -> bool:
        """Check if text looks randomly generated."""
        if len(text) < 6:
            return False

        # Check consonant to vowel ratio
        vowels = sum(1 for c in text.lower() if c in "aeiou")
        if vowels == 0 or len(text) / vowels > 5:
            return True

        # Check for too many consecutive consonants
        consonant_run = 0
        max_run = 0
        for c in text.lower():
            if c.isalpha() and c not in "aeiou":
                consonant_run += 1
                max_run = max(max_run, consonant_run)
            else:
                consonant_run = 0

        if max_run >= 5:
            return True

        # Check for number sequences in the middle
        if re.search(r"[a-z]\d{4,}[a-z]", text.lower()):
            return True

        return False
