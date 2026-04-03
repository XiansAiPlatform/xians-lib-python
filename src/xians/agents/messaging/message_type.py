"""MessageType enum and helpers. Matches C# MessageType + MessageTypeExtensions."""

from enum import Enum
from typing import Optional


class MessageType(str, Enum):
    """Defines the types of messages that can be processed by the platform.
    Matches C# Xians.Lib.Common.Models.MessageType.
    """
    CHAT = "chat"
    DATA = "data"
    WEBHOOK = "webhook"
    HANDOFF = "handoff"
    REASONING = "reasoning"
    TOOL = "tool"
    HEARTBEAT = "heartbeat"

    def to_lower_string(self) -> str:
        return self.value

    @staticmethod
    def parse(value: str, ignore_case: bool = True) -> "MessageType":
        """Parse a string to a MessageType.

        Raises ValueError if the value is not a valid type.
        """
        lookup = value.lower() if ignore_case else value
        for mt in MessageType:
            if mt.value == lookup:
                return mt
        allowed = ", ".join(MessageType.get_allowed_types())
        raise ValueError(f"Invalid message type: {value}. Valid types are: {allowed}")

    @staticmethod
    def try_parse(value: str, ignore_case: bool = True) -> Optional["MessageType"]:
        """Try to parse a string to a MessageType. Returns None on failure."""
        try:
            return MessageType.parse(value, ignore_case)
        except ValueError:
            return None

    @staticmethod
    def get_allowed_types() -> list[str]:
        """Get all allowed message type names in lowercase."""
        return [mt.value for mt in MessageType]

    @staticmethod
    def is_valid(value: str, ignore_case: bool = True) -> bool:
        """Check if a string is a valid message type."""
        return MessageType.try_parse(value, ignore_case) is not None
