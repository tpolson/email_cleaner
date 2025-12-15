"""Data models for email cleaner."""

from .email import Email, EmailHeader
from .classification import JunkClassification, JunkIndicator

__all__ = ["Email", "EmailHeader", "JunkClassification", "JunkIndicator"]
