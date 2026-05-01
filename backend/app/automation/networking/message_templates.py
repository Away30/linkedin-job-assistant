"""Personalized connection request message generation."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


@dataclass
class MessageContext:
    person_name: str
    company_name: str
    role_title: str
    person_title: str
    person_type: str


class MessageTemplateEngine:
    """Generate personalized connection request notes from templates."""

    MAX_LENGTH = 300  # LinkedIn connect note limit

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path
        self._mtime: Optional[float] = None
        self._templates = self._load_defaults()
        self._reload_if_changed()

    def generate(self, context: MessageContext) -> str:
        """Generate a personalized connection note."""
        # Pick up edits made via /connections/messages without a restart.
        self._reload_if_changed()
        template = self._templates.get(
            context.person_type, self._templates["default"]
        )
        first_name = (
            context.person_name.split()[0]
            if context.person_name
            else "there"
        )
        safe_vars = defaultdict(str, {
            "name": first_name,
            "company": context.company_name,
            "role": context.role_title,
            "their_title": context.person_title,
        })
        message = template.format_map(safe_vars)
        return message[: self.MAX_LENGTH]

    def _reload_if_changed(self) -> None:
        path = self._config_path
        if not path or not path.exists():
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if self._mtime is not None and mtime == self._mtime:
            return
        # Reset to defaults so deleted overrides revert cleanly.
        self._templates = self._load_defaults()
        self._load_overrides(path)
        self._mtime = mtime

    def _load_defaults(self) -> dict[str, str]:
        return {
            "recruiter": (
                "Hi {name}, I recently applied for the {role} role at {company}. "
                "I'd love to connect and learn more about the team!"
            ),
            "hiring_manager": (
                "Hi {name}, I applied for the {role} position at {company}. "
                "I'm excited about the work your team is doing and would love to connect."
            ),
            "engineer": (
                "Hi {name}, I applied for the {role} role at {company}. "
                "I'd love to connect and hear about your experience on the team!"
            ),
            "default": (
                "Hi {name}, I'm interested in opportunities at {company} "
                "and would love to connect."
            ),
        }

    def _load_overrides(self, config_path: Path) -> None:
        """Load user-customized templates from YAML."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                overrides = yaml.safe_load(f)
            if overrides and isinstance(overrides, dict):
                for key, value in overrides.items():
                    if isinstance(value, str) and key in self._templates:
                        self._templates[key] = value.strip()
                logger.info("Loaded message template overrides from %s", config_path)
        except Exception as e:
            logger.warning("Failed to load message templates: %s", e)
