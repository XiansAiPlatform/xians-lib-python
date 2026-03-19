"""Xians agents knowledge package.

Provides the KnowledgeCollection facade and provider infrastructure
for agent knowledge management, mirroring C# Xians.Lib.Agents.Knowledge.
"""

from .knowledge_collection import KnowledgeCollection
from .models import KnowledgeItem

__all__ = [
    "KnowledgeCollection",
    "KnowledgeItem",
]
