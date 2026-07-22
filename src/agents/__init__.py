"""Public API for conversational coding agents.

Only the CLI-backed ``Agent`` facade is exported here. Business reviewers such
as ``BuyConfirmationAgent`` should be imported from their concrete module so
callers do not confuse them with Claude/Codex/Cursor conversational backends.
"""

from .agent import Agent

__all__ = ["Agent"]
