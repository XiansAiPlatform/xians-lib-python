"""Register a TRACE log level (numeric 5) mirroring C# LogLevel.Trace.

Industry-standard approach: ``logging.addLevelName`` + ``Logger.trace`` method
added to the Logger class. Same pattern used by ``verboselogs`` and similar
libraries. Must be imported before any logger is used — the ``xians.logging``
package ``__init__`` takes care of this.

After import:

    logger = logging.getLogger(__name__)
    logger.trace("low-level detail")   # works on every Logger instance
"""

from __future__ import annotations

import logging

TRACE: int = 5

_registered = False


def register_trace_level() -> None:
    """Idempotent registration of the TRACE level and Logger.trace method."""
    global _registered
    if _registered:
        return

    logging.addLevelName(TRACE, "TRACE")
    logging.TRACE = TRACE  # type: ignore[attr-defined]

    def _trace(self: logging.Logger, message: object, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)  # type: ignore[arg-type]

    logging.Logger.trace = _trace  # type: ignore[attr-defined]

    _registered = True
