"""Junk email detector agent."""

from dataclasses import dataclass, field
from typing import Callable

from ..config import Config
from ..models import Email, JunkClassification
from ..services import IMAPEmailClient, JunkClassifier


@dataclass
class AgentReport:
    """Report generated after agent run."""

    total_emails_scanned: int = 0
    junk_emails_found: int = 0
    emails_deleted: int = 0
    emails_moved_to_spam: int = 0
    emails_for_review: int = 0
    classifications: list[tuple[Email, JunkClassification]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a summary of the report."""
        lines = [
            "=" * 50,
            "Email Junk Detection Report",
            "=" * 50,
            f"Total emails scanned: {self.total_emails_scanned}",
            f"Junk emails found: {self.junk_emails_found}",
            f"  - High confidence (deleted): {self.emails_deleted}",
            f"  - Medium confidence (spam): {self.emails_moved_to_spam}",
            f"  - Low confidence (review): {self.emails_for_review}",
            f"Clean emails: {self.total_emails_scanned - self.junk_emails_found}",
        ]

        if self.errors:
            lines.append(f"\nErrors encountered: {len(self.errors)}")
            for error in self.errors[:5]:
                lines.append(f"  - {error}")

        lines.append("=" * 50)
        return "\n".join(lines)


class JunkDetectorAgent:
    """Agent that scans emails and identifies junk for deletion."""

    def __init__(self, config: Config):
        """Initialize the agent.

        Args:
            config: Application configuration
        """
        self.config = config
        self.classifier = JunkClassifier(
            confidence_threshold=config.agent.junk_confidence_threshold
        )
        self._progress_callback: Callable[[str], None] | None = None

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback for progress updates.

        Args:
            callback: Function to call with progress messages
        """
        self._progress_callback = callback

    def _log(self, message: str) -> None:
        """Log a progress message."""
        if self._progress_callback:
            self._progress_callback(message)

    def scan_emails(
        self,
        folder: str = "INBOX",
        limit: int | None = None,
        search_criteria: str = "ALL",
    ) -> AgentReport:
        """Scan emails and classify them as junk or not.

        Args:
            folder: Mailbox folder to scan
            limit: Maximum emails to process (overrides config)
            search_criteria: IMAP search criteria

        Returns:
            AgentReport with classification results
        """
        report = AgentReport()
        max_emails = limit or self.config.agent.max_emails_to_process

        self._log(f"Connecting to {self.config.email.imap_server}...")

        try:
            with IMAPEmailClient(self.config.email) as client:
                self._log(f"Scanning folder: {folder}")
                self._log(f"Processing up to {max_emails} emails...")

                for email in client.fetch_emails(
                    folder=folder, limit=max_emails, search_criteria=search_criteria
                ):
                    report.total_emails_scanned += 1

                    try:
                        classification = self.classifier.classify(email)
                        report.classifications.append((email, classification))

                        if classification.is_junk:
                            report.junk_emails_found += 1
                            self._log(
                                f"[JUNK] {email.subject[:50]}... "
                                f"(confidence: {classification.confidence:.2f})"
                            )
                        else:
                            self._log(f"[OK] {email.subject[:50]}...")

                    except Exception as e:
                        report.errors.append(f"Error classifying {email.uid}: {e}")

        except Exception as e:
            report.errors.append(f"Connection error: {e}")
            self._log(f"Error: {e}")

        return report

    def clean_junk(
        self,
        report: AgentReport,
        dry_run: bool | None = None,
    ) -> AgentReport:
        """Clean identified junk emails based on classification.

        Args:
            report: Report from scan_emails with classifications
            dry_run: If True, don't actually delete (overrides config)

        Returns:
            Updated report with action results
        """
        is_dry_run = dry_run if dry_run is not None else self.config.agent.dry_run

        if is_dry_run:
            self._log("\n[DRY RUN] No emails will actually be deleted.\n")

        junk_emails = [
            (email, cls)
            for email, cls in report.classifications
            if cls.is_junk
        ]

        if not junk_emails:
            self._log("No junk emails to clean.")
            return report

        self._log(f"\nProcessing {len(junk_emails)} junk emails...")

        try:
            with IMAPEmailClient(self.config.email) as client:
                for email, classification in junk_emails:
                    action = classification.recommended_action

                    if action == "delete":
                        if is_dry_run:
                            self._log(f"[DRY RUN] Would delete: {email.subject[:50]}...")
                        else:
                            if client.move_to_trash(email.uid, email.folder):
                                report.emails_deleted += 1
                                self._log(f"Deleted: {email.subject[:50]}...")
                            else:
                                report.errors.append(f"Failed to delete {email.uid}")

                    elif action == "move_to_spam":
                        if is_dry_run:
                            self._log(f"[DRY RUN] Would move to spam: {email.subject[:50]}...")
                        else:
                            if client.mark_as_spam(email.uid, email.folder):
                                report.emails_moved_to_spam += 1
                                self._log(f"Moved to spam: {email.subject[:50]}...")
                            else:
                                report.errors.append(f"Failed to move {email.uid} to spam")

                    elif action == "review":
                        report.emails_for_review += 1
                        self._log(
                            f"[REVIEW] {email.subject[:50]}... "
                            f"(confidence: {classification.confidence:.2f})"
                        )

        except Exception as e:
            report.errors.append(f"Error during cleanup: {e}")
            self._log(f"Error: {e}")

        return report

    def run(
        self,
        folder: str = "INBOX",
        limit: int | None = None,
        search_criteria: str = "ALL",
        auto_clean: bool = False,
        dry_run: bool | None = None,
    ) -> AgentReport:
        """Run the full junk detection and cleanup process.

        Args:
            folder: Mailbox folder to process
            limit: Maximum emails to process
            search_criteria: IMAP search criteria
            auto_clean: Automatically clean junk emails
            dry_run: If True, don't actually delete

        Returns:
            AgentReport with full results
        """
        self._log("Starting junk email detection agent...")

        # Scan emails
        report = self.scan_emails(folder, limit, search_criteria)

        # Optionally clean
        if auto_clean and report.junk_emails_found > 0:
            self._log("\nStarting automatic cleanup...")
            report = self.clean_junk(report, dry_run)

        self._log("\n" + report.summary())
        return report

    def get_junk_details(self, report: AgentReport) -> list[dict]:
        """Get detailed information about identified junk emails.

        Args:
            report: Report from scan_emails

        Returns:
            List of dicts with junk email details
        """
        details = []
        for email, classification in report.classifications:
            if classification.is_junk:
                details.append({
                    "uid": email.uid,
                    "subject": email.subject,
                    "sender": email.sender,
                    "sender_name": email.sender_name,
                    "date": email.received_date.isoformat(),
                    "confidence": classification.confidence,
                    "indicators": [ind.value for ind in classification.indicators],
                    "reasons": classification.reasons,
                    "recommended_action": classification.recommended_action,
                })
        return details
