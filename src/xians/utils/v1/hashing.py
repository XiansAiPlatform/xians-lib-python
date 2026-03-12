"""Hashing utilities for Xians SDK v1."""

import hashlib
import json


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_definition_hash(definition: dict) -> str:
    """Compute SHA-256 hash of a workflow definition.

    Matches C# WorkflowDefinitionUploader hash logic:
    SHA256(JSON.Serialize(definition))
    """
    json_str = json.dumps(definition, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


__all__ = ["compute_hash", "compute_definition_hash"]
