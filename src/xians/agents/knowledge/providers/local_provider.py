"""Local in-memory knowledge provider. Mirrors C# LocalKnowledgeProvider.

Used when XiansOptions.local_mode is True, for development and testing
without a running Xians Server. Knowledge is stored entirely in memory,
with an optional file-based fallback.

C# uses .NET embedded resources; Python has no equivalent, so we use a
local directory instead. The directory path is resolved from the
LOCAL_KNOWLEDGE_FOLDER environment variable (matching the C# .env
convention) or can be passed explicitly.

C# naming convention:
    {AgentName}.Knowledge.{KnowledgeName}.{ext}

Python file-system equivalent:
    {knowledge_dir}/{KnowledgeName}.{ext}            (flat, primary)
    {knowledge_dir}/{AgentName}/{KnowledgeName}.{ext} (subfolder fallback)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from ..models import KnowledgeItem

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = (".md", ".txt", ".json")

_EXT_TO_TYPE = {
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
}


def _infer_knowledge_type(ext: str) -> str:
    """Infer the knowledge type from a file extension. Mirrors C# InferKnowledgeType."""
    return _EXT_TO_TYPE.get(ext.lower(), "text")


class LocalKnowledgeProvider:
    """In-memory knowledge provider for local development and testing.

    Mirrors C# LocalKnowledgeProvider:
    - get/update/delete operate against an in-memory dict.
    - get falls back to loading from a local knowledge folder.

    The knowledge folder is resolved in order:
    1. Explicit ``knowledge_dir`` parameter (if provided).
    2. ``LOCAL_KNOWLEDGE_FOLDER`` environment variable (matches C# .env convention).
    3. No file fallback (in-memory only).
    """

    def __init__(
        self,
        knowledge_dir: str | Path | None = None,
    ) -> None:
        self._store: dict[str, KnowledgeItem] = {}

        if knowledge_dir is not None:
            self._knowledge_dir: Path | None = Path(knowledge_dir)
        else:
            env_dir = os.environ.get("LOCAL_KNOWLEDGE_FOLDER")
            self._knowledge_dir = Path(env_dir) if env_dir else None

        if self._knowledge_dir:
            logger.debug(
                "[LocalMode] Knowledge directory: %s (exists=%s)",
                self._knowledge_dir.resolve(),
                self._knowledge_dir.is_dir(),
            )

    # ------------------------------------------------------------------
    # IKnowledgeProvider
    # ------------------------------------------------------------------

    async def get_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        key = self._store_key(tenant_id, agent_name, activation_name, knowledge_name)
        item = self._store.get(key)
        if item is not None:
            return item

        system_key = self._store_key("system", agent_name, activation_name, knowledge_name)
        item = self._store.get(system_key)
        if item is not None:
            return item

        return self._load_from_file(agent_name, knowledge_name)

    async def get_system_async(
        self,
        knowledge_name: str,
        agent_name: str,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        key = self._store_key("system", agent_name, activation_name, knowledge_name)
        item = self._store.get(key)
        if item is not None:
            return item
        return self._load_from_file(agent_name, knowledge_name)

    async def update_async(
        self,
        knowledge_name: str,
        content: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        type: Optional[str] = None,
        system_scoped: bool = False,
        activation_name: Optional[str] = None,
        description: Optional[str] = None,
        visible: bool = True,
    ) -> bool:
        scope = "system" if system_scoped else tenant_id
        key = self._store_key(scope, agent_name, activation_name, knowledge_name)
        self._store[key] = KnowledgeItem(
            name=knowledge_name,
            content=content,
            type=type,
            agent=agent_name,
            tenant_id=tenant_id,
            system_scoped=system_scoped,
            description=description,
            visible=visible,
        )
        logger.debug("Local knowledge updated: %s", key)
        return True

    async def delete_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> bool:
        key = self._store_key(tenant_id, agent_name, activation_name, knowledge_name)
        removed = self._store.pop(key, None)
        if removed:
            logger.debug("Local knowledge deleted: %s", key)
        return removed is not None

    async def list_async(
        self,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> list[KnowledgeItem]:
        results: list[KnowledgeItem] = []
        for key, item in self._store.items():
            if f":{agent_name}:" in key:
                results.append(item)
        return results

    # ------------------------------------------------------------------
    # File-based fallback (mirrors C# LoadFromEmbeddedResource)
    #
    # C# convention: {AgentName}.Knowledge.{KnowledgeName}.{ext}
    # Python adaptation: search for {KnowledgeName}.{ext} in:
    #   1. {knowledge_dir}/  (flat, like C# embedded resource naming)
    #   2. {knowledge_dir}/{AgentName}/  (subfolder convention)
    # With fallback normalization (replace spaces/dashes, lowercase).
    # ------------------------------------------------------------------

    def _load_from_file(
        self,
        agent_name: str,
        knowledge_name: str,
    ) -> Optional[KnowledgeItem]:
        if self._knowledge_dir is None:
            return None

        normalized_name = (
            knowledge_name
            .replace(" ", "-")
            .lower()
        )

        search_dirs: list[Path] = []
        agent_subdir = self._knowledge_dir / agent_name
        if agent_subdir.is_dir():
            search_dirs.append(agent_subdir)
        search_dirs.append(self._knowledge_dir)

        searched: list[str] = []

        for search_dir in search_dirs:
            for ext in _SUPPORTED_EXTENSIONS:
                candidates = [
                    knowledge_name + ext,
                    normalized_name + ext,
                ]
                for candidate_name in candidates:
                    candidate = search_dir / candidate_name
                    searched.append(str(candidate))
                    if candidate.is_file():
                        try:
                            content = candidate.read_text(encoding="utf-8")
                            ktype = _infer_knowledge_type(ext)
                            logger.debug(
                                "[LocalMode] Loaded knowledge from file: Name=%s in %s",
                                knowledge_name,
                                candidate,
                            )
                            return KnowledgeItem(
                                name=knowledge_name,
                                content=content,
                                type=ktype,
                                agent=agent_name,
                                system_scoped=True,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to read knowledge file: %s",
                                candidate,
                                exc_info=True,
                            )

                # Suffix fallback: any file ending with .{normalizedName}.{ext}
                # Mirrors C# TryLoadResourceBySuffix
                suffix = f".{normalized_name}{ext}"
                try:
                    for path in search_dir.iterdir():
                        if path.is_file() and path.name.lower().endswith(suffix):
                            try:
                                content = path.read_text(encoding="utf-8")
                                ktype = _infer_knowledge_type(ext)
                                logger.debug(
                                    "[LocalMode] Loaded knowledge by suffix match: Name=%s in %s",
                                    knowledge_name,
                                    path,
                                )
                                return KnowledgeItem(
                                    name=knowledge_name,
                                    content=content,
                                    type=ktype,
                                    agent=agent_name,
                                    system_scoped=True,
                                )
                            except Exception:
                                logger.warning(
                                    "Failed to read knowledge file: %s",
                                    path,
                                    exc_info=True,
                                )
                except OSError:
                    pass

        logger.warning(
            "[LocalMode] Knowledge not found. Name=%s, Agent=%s. Searched: [%s]",
            knowledge_name,
            agent_name,
            ", ".join(searched),
        )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _store_key(
        tenant_id: Optional[str],
        agent_name: str,
        activation_name: Optional[str],
        knowledge_name: str,
    ) -> str:
        return (
            f"{tenant_id or 'system'}:{agent_name}"
            f":{activation_name or 'default'}:{knowledge_name}"
        )
