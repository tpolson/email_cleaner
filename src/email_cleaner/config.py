"""Configuration management for the email cleaner agent."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class EmailConfig:
    """Email server configuration."""

    imap_server: str
    imap_port: int
    email_address: str
    email_password: str


@dataclass
class AgentConfig:
    """Agent behavior configuration."""

    dry_run: bool
    max_emails_to_process: int
    junk_confidence_threshold: float


@dataclass
class Config:
    """Main configuration container."""

    email: EmailConfig
    agent: AgentConfig


def load_config(env_file: Path | None = None) -> Config:
    """Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file

    Returns:
        Config object with all settings
    """
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    email_config = EmailConfig(
        imap_server=os.getenv("IMAP_SERVER", "imap.gmail.com"),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        email_address=os.getenv("EMAIL_ADDRESS", ""),
        email_password=os.getenv("EMAIL_PASSWORD", ""),
    )

    agent_config = AgentConfig(
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
        max_emails_to_process=int(os.getenv("MAX_EMAILS_TO_PROCESS", "100")),
        junk_confidence_threshold=float(os.getenv("JUNK_CONFIDENCE_THRESHOLD", "0.7")),
    )

    return Config(email=email_config, agent=agent_config)
