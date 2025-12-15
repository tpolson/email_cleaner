"""IMAP client for fetching and managing emails."""

import email
from email.header import decode_header
from datetime import datetime
from typing import Generator
import imaplib
import ssl

from ..config import EmailConfig
from ..models import Email, EmailHeader


class IMAPEmailClient:
    """Client for interacting with email servers via IMAP."""

    def __init__(self, config: EmailConfig):
        """Initialize the IMAP client.

        Args:
            config: Email server configuration
        """
        self.config = config
        self._connection: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        """Establish connection to the IMAP server."""
        context = ssl.create_default_context()
        self._connection = imaplib.IMAP4_SSL(
            self.config.imap_server, self.config.imap_port, ssl_context=context
        )
        self._connection.login(self.config.email_address, self.config.email_password)

    def disconnect(self) -> None:
        """Close the IMAP connection."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def __enter__(self) -> "IMAPEmailClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def list_folders(self) -> list[str]:
        """List all available mailbox folders."""
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        status, folders = self._connection.list()
        if status != "OK":
            return []

        result = []
        for folder in folders:
            if isinstance(folder, bytes):
                # Parse folder name from response like: b'(\\HasNoChildren) "/" "INBOX"'
                parts = folder.decode().split('"')
                if len(parts) >= 2:
                    result.append(parts[-2])
        return result

    def select_folder(self, folder: str = "INBOX") -> int:
        """Select a mailbox folder.

        Args:
            folder: Folder name to select

        Returns:
            Number of messages in the folder
        """
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        status, data = self._connection.select(folder)
        if status != "OK":
            raise RuntimeError(f"Failed to select folder: {folder}")

        return int(data[0])

    def fetch_emails(
        self, folder: str = "INBOX", limit: int = 100, search_criteria: str = "ALL"
    ) -> Generator[Email, None, None]:
        """Fetch emails from the specified folder.

        Args:
            folder: Mailbox folder to fetch from
            limit: Maximum number of emails to fetch
            search_criteria: IMAP search criteria (e.g., "ALL", "UNSEEN", "SINCE 01-Jan-2024")

        Yields:
            Email objects
        """
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        self.select_folder(folder)

        # Search for emails
        status, data = self._connection.search(None, search_criteria)
        if status != "OK":
            return

        email_ids = data[0].split()
        # Get most recent emails first
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        email_ids = reversed(email_ids)  # Most recent first

        for email_id in email_ids:
            try:
                email_obj = self._fetch_single_email(email_id, folder)
                if email_obj:
                    yield email_obj
            except Exception as e:
                print(f"Error fetching email {email_id}: {e}")
                continue

    def _fetch_single_email(self, email_id: bytes, folder: str) -> Email | None:
        """Fetch a single email by ID."""
        status, data = self._connection.fetch(email_id, "(RFC822 UID)")
        if status != "OK" or not data or not data[0]:
            return None

        # Extract UID and raw message
        uid = int(email_id)
        for part in data:
            if isinstance(part, tuple):
                # Try to extract UID from response
                if b"UID" in part[0]:
                    uid_str = part[0].decode()
                    if "UID " in uid_str:
                        uid = int(uid_str.split("UID ")[1].split()[0])
                raw_email = part[1]
                break
        else:
            return None

        msg = email.message_from_bytes(raw_email)
        return self._parse_email(msg, uid, folder)

    def _parse_email(
        self, msg: email.message.Message, uid: int, folder: str
    ) -> Email:
        """Parse an email message into our Email model."""
        # Decode subject
        subject = self._decode_header_value(msg.get("Subject", ""))

        # Parse sender
        from_header = msg.get("From", "")
        sender_name, sender_email = self._parse_address(from_header)

        # Parse recipients
        to_header = msg.get("To", "")
        recipients = [
            addr.strip() for addr in to_header.split(",") if addr.strip()
        ]

        # Parse date
        date_str = msg.get("Date", "")
        received_date = self._parse_date(date_str)

        # Extract body
        body_text, body_html = self._extract_body(msg)

        # Extract headers
        headers = [
            EmailHeader(name=key, value=self._decode_header_value(value))
            for key, value in msg.items()
        ]

        # Check for attachments
        has_attachments = any(
            part.get_content_disposition() == "attachment"
            for part in msg.walk()
            if part.get_content_disposition()
        )

        return Email(
            uid=uid,
            message_id=msg.get("Message-ID", ""),
            sender=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            received_date=received_date,
            headers=headers,
            has_attachments=has_attachments,
            folder=folder,
        )

    def _decode_header_value(self, value: str) -> str:
        """Decode an email header value."""
        if not value:
            return ""

        decoded_parts = []
        for part, encoding in decode_header(value):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded_parts.append(part)
        return "".join(decoded_parts)

    def _parse_address(self, address: str) -> tuple[str, str]:
        """Parse an email address into name and email."""
        address = self._decode_header_value(address)
        if "<" in address and ">" in address:
            name = address.split("<")[0].strip().strip('"')
            email_addr = address.split("<")[1].split(">")[0].strip()
        else:
            name = ""
            email_addr = address.strip()
        return name, email_addr

    def _parse_date(self, date_str: str) -> datetime:
        """Parse an email date string."""
        from email.utils import parsedate_to_datetime

        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.now()

    def _extract_body(
        self, msg: email.message.Message
    ) -> tuple[str, str]:
        """Extract plain text and HTML body from email."""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="replace")

                        if content_type == "text/plain":
                            body_text = text
                        elif content_type == "text/html":
                            body_html = text
                except Exception:
                    continue
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")

                    if content_type == "text/plain":
                        body_text = text
                    elif content_type == "text/html":
                        body_html = text
            except Exception:
                pass

        return body_text, body_html

    def move_to_trash(self, uid: int, folder: str = "INBOX") -> bool:
        """Move an email to trash.

        Args:
            uid: Email UID
            folder: Current folder of the email

        Returns:
            True if successful
        """
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        self.select_folder(folder)

        # Try common trash folder names
        trash_folders = ["[Gmail]/Trash", "Trash", "Deleted Items", "Deleted"]

        for trash_folder in trash_folders:
            try:
                # Copy to trash
                status, _ = self._connection.uid("COPY", str(uid), trash_folder)
                if status == "OK":
                    # Mark original as deleted
                    self._connection.uid("STORE", str(uid), "+FLAGS", "\\Deleted")
                    self._connection.expunge()
                    return True
            except Exception:
                continue

        return False

    def mark_as_spam(self, uid: int, folder: str = "INBOX") -> bool:
        """Move an email to spam/junk folder.

        Args:
            uid: Email UID
            folder: Current folder of the email

        Returns:
            True if successful
        """
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        self.select_folder(folder)

        # Try common spam folder names
        spam_folders = ["[Gmail]/Spam", "Spam", "Junk", "Junk E-mail"]

        for spam_folder in spam_folders:
            try:
                status, _ = self._connection.uid("COPY", str(uid), spam_folder)
                if status == "OK":
                    self._connection.uid("STORE", str(uid), "+FLAGS", "\\Deleted")
                    self._connection.expunge()
                    return True
            except Exception:
                continue

        return False

    def delete_email(self, uid: int, folder: str = "INBOX") -> bool:
        """Permanently delete an email.

        Args:
            uid: Email UID
            folder: Current folder of the email

        Returns:
            True if successful
        """
        if not self._connection:
            raise RuntimeError("Not connected to IMAP server")

        self.select_folder(folder)

        try:
            self._connection.uid("STORE", str(uid), "+FLAGS", "\\Deleted")
            self._connection.expunge()
            return True
        except Exception:
            return False
