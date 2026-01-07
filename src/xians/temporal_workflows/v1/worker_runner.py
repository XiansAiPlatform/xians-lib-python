"""Temporal worker host and runner for Xians SDK v1."""

import asyncio
import base64
import logging
from typing import Any, Callable

from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

from ...exceptions.v1.errors import TemporalError
from ...models.v1.configs import TemporalConfig

logger = logging.getLogger(__name__)


def build_task_queue_name(
    agent_key: str,
    workflow_name: str,
    tenant_id: str | None = None,
    system_scoped: bool = False,
) -> str:
    """
    Build a deterministic task queue name for Temporal routing.
    """
    scope = "system" if system_scoped else "user"
    tenant_part = tenant_id if tenant_id else "default"

    return f"xians-{tenant_part}-{scope}-{agent_key}-{workflow_name}"


class WorkerHost:
    """
    Manages Temporal worker lifecycle.
    """

    def __init__(self, temporal_config: TemporalConfig) -> None:
        self.config = temporal_config
        self.client: Client | None = None
        self.workers: list[Worker] = []
        self._workflows: list[type] = []
        self._activities: list[Callable] = []

    async def connect(self) -> None:
        try:
            target = f"{self.config.host}:{self.config.port}"
            tls_config = None
            if self.config.tls_enabled:
                server_root = (
                    base64.b64decode(self.config.server_root_ca_cert_base64.get_secret_value())
                    if self.config.server_root_ca_cert_base64
                    else None
                )
                client_cert = (
                    base64.b64decode(self.config.client_cert_base64.get_secret_value())
                    if self.config.client_cert_base64
                    else None
                )
                client_key = (
                    base64.b64decode(self.config.client_private_key_base64.get_secret_value())
                    if self.config.client_private_key_base64
                    else None
                )
                if (client_cert and not client_key) or (client_key and not client_cert):
                    raise TemporalError("Both client_cert_base64 and client_private_key_base64 must be provided for mTLS")
                if not server_root and not client_cert and not client_key and self.config.tls_cert_path:
                    with open(self.config.tls_cert_path, "rb") as f:
                        server_root = f.read()

                tls_config = TLSConfig(
                    server_root_ca_cert=server_root,
                    client_cert=client_cert,
                    client_private_key=client_key,
                )

            self.client = await Client.connect(
                target,
                namespace=self.config.namespace,
                tls=tls_config,
            )

            logger.info(
                f"Connected to Temporal server at {target}, namespace: {self.config.namespace}"
            )

        except Exception as e:
            raise TemporalError(
                f"Failed to connect to Temporal server: {str(e)}",
                cause=e,
            )

    def register_workflow(self, workflow_class: type) -> None:
        self._workflows.append(workflow_class)
        logger.debug(f"Registered workflow: {workflow_class.__name__}")

    def register_activity(self, activity_func: Callable) -> None:
        self._activities.append(activity_func)
        logger.debug(f"Registered activity: {activity_func.__name__}")

    async def start_worker(
        self,
        task_queue: str,
        workflows: list[type] | None = None,
        activities: list[Callable] | None = None,
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
        activities: list[Callable] | None = None,
        workers_per_queue: int = 1,
    ) -> None:
        for task_queue in task_queues:
            for i in range(workers_per_queue):
                await self.start_worker(
                    task_queue=task_queue,
                    workflows=workflows,
                    activities=activities,
                )
                logger.debug(f"Started worker {i+1}/{workers_per_queue} for queue {task_queue}")

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


class WorkerRegistry:

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._registrations: dict[str, dict[str, Any]] = {}

    def register(
        self,
        agent_key: str,
        workflow_name: str,
        workflow_class: type,
        activity_func: Callable,
        tenant_id: str | None = None,
        system_scoped: bool = False,
        workers: int = 1,
    ) -> str:
        task_queue = build_task_queue_name(
            agent_key=agent_key,
            workflow_name=workflow_name,
            tenant_id=tenant_id,
            system_scoped=system_scoped,
        )

        self._registrations[task_queue] = {
            "agent_key": agent_key,
            "workflow_name": workflow_name,
            "workflow_class": workflow_class,
            "activity_func": activity_func,
            "workers": workers,
        }

        logger.debug(f"Registered {workflow_name} for {agent_key} on queue {task_queue}")
        return task_queue

    def get_all_task_queues(self) -> list[str]:
        return list(self._registrations.keys())

    def get_workflows_for_queue(self, task_queue: str) -> list[type]:
        reg = self._registrations.get(task_queue)
        return [reg["workflow_class"]] if reg else []

    def get_activities_for_queue(self, task_queue: str) -> list[Callable]:
        reg = self._registrations.get(task_queue)
        return [reg["activity_func"]] if reg else []

    def get_worker_count(self, task_queue: str) -> int:
        reg = self._registrations.get(task_queue)
        return reg["workers"] if reg else 1


__all__ = [
    "WorkerHost",
    "WorkerRegistry",
    "build_task_queue_name",
]

