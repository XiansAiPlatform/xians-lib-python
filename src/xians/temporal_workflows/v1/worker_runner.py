"""Temporal worker host and runner for Xians SDK v1.

Task queue naming aligned with C# TenantContext.GetTaskQueueName:
- System-scoped: "{workflowType}"
- Tenant-scoped: "{tenantId}:{workflowType}"
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from temporalio.client import Client, TLSConfig
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from ...exceptions.v1.errors import ConfigurationError, TemporalError
from ...models.v1.configs import TemporalConfig, TemporalTLSConfig
from .tls_utils import resolve_cert_bytes, TLSMaterialError

logger = logging.getLogger(__name__)


# Xians runs workflows without Temporal's Python sandbox so that Python workers
# behave identically to the C# agent library (which has no sandbox).  The C#
# SDK relies on .NET runtime hooks to enforce determinism; Python without the
# sandbox places that responsibility on workflow authors — the same contract
# used in the C# library.  All Xians workflows only call deterministic Temporal
# APIs (``workflow.info``, ``workflow.memo``, ``workflow.execute_activity`` …)
# so no sandbox is required to guarantee replay safety.
_XIANS_WORKFLOW_RUNNER = UnsandboxedWorkflowRunner()


def build_task_queue_name(
    workflow_type: str,
    system_scoped: bool,
    tenant_id: Optional[str] = None,
) -> str:
    """Build task queue name matching C# TenantContext.GetTaskQueueName().

    Args:
        workflow_type: Format "{AgentName}:{WorkflowName}"
        system_scoped: If True, no tenant prefix
        tenant_id: Required if not system_scoped

    Returns:
        Task queue name:
        - System-scoped: "{workflowType}"
        - Tenant-scoped: "{tenantId}:{workflowType}"
    """
    if system_scoped:
        return workflow_type
    if not tenant_id:
        raise ConfigurationError("tenant_id is required for non-system-scoped workflows")
    return f"{tenant_id}:{workflow_type}"


@dataclass
class WorkerRegistration:
    """Registration entry for a Temporal worker."""
    task_queue: str
    workflow_class: type
    activity_instances: list = field(default_factory=list)
    workers: int = 1


class WorkerHost:
    """Manages Temporal worker lifecycle."""

    def __init__(self, temporal_config: TemporalConfig) -> None:
        self.config = temporal_config
        self.client: Client | None = None
        self.workers: list[Worker] = []
        self._workflows: list[type] = []
        self._activities: list[Callable] = []

    def _build_temporal_tls_config(self, tls_cfg: TemporalTLSConfig | None) -> TLSConfig | None:
        if not tls_cfg:
            return None
        any_material = any(
            [
                tls_cfg.root_ca_pem,
                tls_cfg.root_ca_path,
                tls_cfg.client_cert_pem,
                tls_cfg.client_cert_path,
                tls_cfg.client_key_pem,
                tls_cfg.client_key_path,
            ]
        )
        if not tls_cfg.enabled and not any_material:
            return None

        server_root = resolve_cert_bytes(tls_cfg.root_ca_pem, tls_cfg.root_ca_path, tls_cfg.pem_is_base64)
        client_cert = resolve_cert_bytes(tls_cfg.client_cert_pem, tls_cfg.client_cert_path, tls_cfg.pem_is_base64)
        client_key = resolve_cert_bytes(tls_cfg.client_key_pem, tls_cfg.client_key_path, tls_cfg.pem_is_base64)

        if (client_cert and not client_key) or (client_key and not client_cert):
            raise TemporalError(
                "mTLS requires both client cert and private key. Provide client_cert_* and client_key_*."
            )

        return TLSConfig(
            server_root_ca_cert=server_root,
            client_cert=client_cert,
            client_private_key=client_key,
            domain=tls_cfg.domain,
        )

    async def connect(self) -> None:
        try:
            target = self.config.address
            tls_config = self._build_temporal_tls_config(self.config.tls)

            self.client = await Client.connect(
                target,
                namespace=self.config.namespace,
                tls=tls_config,
            )

            logger.info(
                f"Connected to Temporal server at {target}, namespace: {self.config.namespace}"
            )

        except TLSMaterialError as e:
            raise TemporalError(f"Failed to load TLS materials: {e}") from e
        except Exception as e:
            tls = self.config.tls
            tls_enabled = bool(tls and (tls.enabled or any([
                tls.root_ca_pem, tls.root_ca_path, tls.client_cert_pem,
                tls.client_cert_path, tls.client_key_pem, tls.client_key_path,
            ]))) if tls else False

            msg = (
                f"Failed to connect to Temporal {self.config.address} "
                f"(namespace={self.config.namespace}). TLS enabled={tls_enabled}. "
                f"Underlying error: {e}"
            )
            err_str = str(e)
            if "UnknownIssuer" in err_str or "CERTIFICATE_VERIFY_FAILED" in err_str:
                msg += (
                    " Hint: For private CA, provide TemporalConfig.tls.root_ca_pem or root_ca_path."
                )
            elif "dns error" in err_str.lower() or "nodename nor servname" in err_str:
                msg += f" Hint: DNS resolution failed for '{self.config.address}'."

            raise TemporalError(msg, cause=e)

    def register_workflow(self, workflow_class: type) -> None:
        self._workflows.append(workflow_class)
        logger.debug(f"Registered workflow: {workflow_class.__name__}")

    def register_activity(self, activity_func: Callable) -> None:
        self._activities.append(activity_func)
        logger.debug(f"Registered activity: {getattr(activity_func, '__name__', str(activity_func))}")

    async def start_worker(
        self,
        task_queue: str,
        workflows: list[type] | None = None,
        activities: list[Callable | Any] | None = None,
        max_concurrent_activities: int = 10,
    ) -> Worker:
        if not self.client:
            raise TemporalError("Must call connect() before starting workers")

        try:
            worker = Worker(
                self.client,
                task_queue=task_queue,
                workflows=workflows or self._workflows,
                activities=activities or self._activities,
                max_concurrent_activities=max_concurrent_activities,
                # Parity with the C# agent library — see ``_XIANS_WORKFLOW_RUNNER``.
                workflow_runner=_XIANS_WORKFLOW_RUNNER,
            )

            asyncio.create_task(worker.run())

            self.workers.append(worker)
            logger.info(
                f"Started worker on task queue: {task_queue} "
                f"with {len(workflows or self._workflows)} workflows, "
                f"{len(activities or self._activities)} activities"
            )

            return worker

        except Exception as e:
            raise TemporalError(
                f"Failed to start worker on task queue {task_queue}: {str(e)}",
                cause=e,
            )

    async def start_workers(
        self,
        task_queues: list[str],
        workflows: list[type] | None = None,
        activities: list[Callable | Any] | None = None,
        workers_per_queue: int = 1,
    ) -> None:
        if workers_per_queue > 1:
            logger.warning(
                "Multiple workers per task queue in the same process are not supported. "
                "Creating a single worker per queue."
            )
        for task_queue in task_queues:
            existing = [w for w in self.workers if w.task_queue == task_queue]
            if existing:
                logger.debug(f"Worker for task queue '{task_queue}' already exists; skipping.")
                continue
            await self.start_worker(
                task_queue=task_queue,
                workflows=workflows,
                activities=activities,
            )

    async def shutdown(self) -> None:
        logger.info(f"Shutting down {len(self.workers)} workers...")
        for worker in self.workers:
            try:
                await worker.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down worker: {e}")
        self.workers.clear()
        logger.info("All workers shut down")

    async def run_until_stopped(self) -> None:
        if not self.workers:
            raise TemporalError("No workers started. Call start_worker() first.")

        logger.info(f"Running {len(self.workers)} workers. Press Ctrl+C to stop.")

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Received cancellation signal")
        finally:
            await self.shutdown()

    @staticmethod
    def _get_activity_methods(instance: object) -> list:
        """Extract all @activity.defn methods from an activity class instance."""
        from temporalio import activity as temporal_activity
        methods = []
        for name in dir(instance):
            if name.startswith("_"):
                continue
            attr = getattr(instance, name, None)
            if callable(attr) and hasattr(attr, "__temporal_activity_definition"):
                methods.append(attr)
        return methods


class WorkerRegistry:
    """Registry for worker registrations."""

    def __init__(self) -> None:
        self._registrations: dict[str, WorkerRegistration] = {}

    def register(
        self,
        workflow_type: str,
        system_scoped: bool,
        tenant_id: Optional[str],
        workflow_class: type,
        workers: int = 1,
        activity_instances: list | None = None,
    ) -> str:
        task_queue = build_task_queue_name(
            workflow_type=workflow_type,
            system_scoped=system_scoped,
            tenant_id=tenant_id,
        )

        self._registrations[task_queue] = WorkerRegistration(
            task_queue=task_queue,
            workflow_class=workflow_class,
            activity_instances=activity_instances or [],
            workers=workers,
        )

        logger.debug(f"Registered workflow {workflow_type} on queue {task_queue}")
        return task_queue

    def get_all_task_queues(self) -> list[str]:
        return list(self._registrations.keys())

    def get_registration(self, task_queue: str) -> Optional[WorkerRegistration]:
        return self._registrations.get(task_queue)

    def get_workflows_for_queue(self, task_queue: str) -> list[type]:
        reg = self._registrations.get(task_queue)
        return [reg.workflow_class] if reg else []

    def get_activities_for_queue(self, task_queue: str) -> list:
        reg = self._registrations.get(task_queue)
        if not reg:
            return []
        activities = []
        for instance in reg.activity_instances:
            activities.extend(WorkerHost._get_activity_methods(instance))
        return activities

    def get_worker_count(self, task_queue: str) -> int:
        reg = self._registrations.get(task_queue)
        return reg.workers if reg else 1


__all__ = [
    "WorkerHost",
    "WorkerRegistry",
    "WorkerRegistration",
    "build_task_queue_name",
]
