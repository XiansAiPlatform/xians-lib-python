"""Main platform facade for Xians SDK v1."""

import logging
from typing import Callable

from temporalio.client import Client

from ...configs.v1.logging import configure_logging
from ...constants.v1.core import WorkflowType
from ...exceptions.v1.errors import ConfigurationError, TemporalError
from ...middleware.v1 import (
    initialize_middleware,
)
from ...models.v1.configs import TemporalConfig, XiansOptions, XiansServerConfig
from ...models.v1.configs import TemporalTLSConfig
from ...models.v1.entities import AgentDefinition, WorkflowDefinition
from ...temporal_workflows.v1.worker_runner import WorkerHost, WorkerRegistry
from ...temporal_workflows.v1.workflows import ConversationWorkflow, InvokeAgentWorkflow
from ..v1.agent_client import AgentClient
from ..v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class AgentRegistration:
    """
    Represents a registered agent with workflow configuration.
    """

    def __init__(
        self,
        platform: "XiansPlatform",
        definition: AgentDefinition,
    ) -> None:
        """
        Initialize agent registration.
        """
        self.platform = platform
        self.definition = definition
        self.workflows: list[WorkflowDefinition] = []

    def _define_workflow(
        self,
        workflow_type: WorkflowType,
        workflow_class: type,
        name: str,
        workers: int,
        activity_func: Callable | None,
    ) -> WorkflowDefinition:
        """
        Internal helper to define a workflow for this agent.
        """
        workflow_def = WorkflowDefinition(
            workflow_type=workflow_type,
            name=name,
            workers=workers,
            agent_key=self.definition.agent_key or self.definition.name,
            activity_name=activity_func.__name__ if activity_func else "execute_agent_activity",
        )

        self.workflows.append(workflow_def)

        if activity_func:
            self.platform._worker_registry.register(
                agent_key=workflow_def.agent_key,
                workflow_name=workflow_def.name,
                workflow_class=workflow_class,
                activity_func=activity_func,
                system_scoped=self.definition.system_scoped,
                workers=workers,
            )

        logger.info(f"Defined {workflow_type} workflow '{name}' for agent '{self.definition.name}'")
        return workflow_def

    def define_invoke_workflow(
        self,
        name: str = "InvokeAgent",
        workers: int = 1,
        activity_func: Callable | None = None,
    ) -> WorkflowDefinition:
        """
        Define a task-based (invoke) workflow for this agent.
        """
        from ...constants.v1.core import WorkflowType

        return self._define_workflow(
            workflow_type=WorkflowType.TASK_BASED,
            workflow_class=InvokeAgentWorkflow,
            name=name,
            workers=workers,
            activity_func=activity_func,
        )

    def define_conversation_workflow(
        self,
        name: str = "Conversation",
        workers: int = 1,
        activity_func: Callable | None = None,
    ) -> WorkflowDefinition:
        """
        Define a conversational (long-running) workflow for this agent.
        """
        from ...constants.v1.core import WorkflowType

        return self._define_workflow(
            workflow_type=WorkflowType.CONVERSATIONAL,
            workflow_class=ConversationWorkflow,
            name=name,
            workers=workers,
            activity_func=activity_func,
        )


class AgentRegistry:
    """
    Registry for managing agent definitions and workflows.
    """

    def __init__(self, platform: "XiansPlatform") -> None:
        self.platform = platform
        self._agents: dict[str, AgentRegistration] = {}

    def register(
        self,
        name: str,
        description: str | None = None,
        system_scoped: bool = False,
    ) -> AgentRegistration:
        definition = AgentDefinition(
            name=name,
            description=description,
            system_scoped=system_scoped,
            agent_key=name,  # Use name as key for now
        )

        agent_reg = AgentRegistration(self.platform, definition)
        self._agents[name] = agent_reg

        logger.info(f"Registered agent: {name} (system_scoped={system_scoped})")
        return agent_reg

    def get(self, name: str) -> AgentRegistration | None:
        return self._agents.get(name)

    def all(self) -> list[AgentRegistration]:
        return list(self._agents.values())


class XiansPlatform:
    """
    Main entry point for Xians SDK.
    """

    def __init__(
        self,
        options: XiansOptions,
        xians_client: XiansServerClient,
        temporal_config: TemporalConfig,
    ) -> None:
        """
        Initialize platform (use XiansPlatform.initialize() instead).
        """
        self.options = options
        self.xians_client = xians_client
        self.temporal_config = temporal_config

        self._worker_host: WorkerHost | None = None
        self._worker_registry = WorkerRegistry()
        self._temporal_client: Client | None = None

        self.agents = AgentRegistry(self)

    @classmethod
    async def initialize(cls, options: XiansOptions) -> "XiansPlatform":
        """
        Initialize the Xians platform.
        """
        initialize_middleware()
        logger.info("Exception handler middleware initialized")

        configure_logging(
            log_level=options.log_level,
            enable_structured=options.enable_structured_logging,
        )

        logger.info("Initializing Xians Platform...")

        server_config = XiansServerConfig(
            server_url=options.server_url,
            auth_mode=options.server_auth_mode,
            api_key=options.server_api_key,
            x_api_key=options.server_x_api_key,
            tenant_id=options.tenant_id,
        )
        xians_client = XiansServerClient(server_config)

        temporal_config = options.temporal
        if temporal_config is None:
            logger.info("Fetching Temporal settings from Xians Server...")
            try:
                settings = await xians_client.fetch_temporal_settings()
                temporal_config = cls._build_temporal_config_from_settings(settings)
                logger.info(f"Using Temporal at {temporal_config.address}")
                # Debug TLS summary without sensitive contents
                tls = temporal_config.tls
                tls_enabled = bool(tls and (tls.enabled or any([
                    tls.root_ca_pem,
                    tls.root_ca_path,
                    tls.client_cert_pem,
                    tls.client_cert_path,
                    tls.client_key_pem,
                    tls.client_key_path,
                ])))
                root_ca_provided = bool(tls and (tls.root_ca_pem or tls.root_ca_path))
                mtls_provided = bool(tls and ((tls.client_cert_pem or tls.client_cert_path) and (tls.client_key_pem or tls.client_key_path)))
                domain_override = tls.domain if tls else None
                logger.debug(
                    f"Temporal settings: namespace={temporal_config.namespace}, tls_enabled={tls_enabled}, "
                    f"root_ca_provided={root_ca_provided}, mtls_provided={mtls_provided}, domain_override={domain_override}"
                )
            except Exception as e:
                raise ConfigurationError(
                    "Failed to fetch Temporal settings from Xians Server",
                    cause=e,
                )

        platform = cls(options, xians_client, temporal_config)

        logger.info("Xians Platform initialized successfully")
        return platform

    async def run_all(self) -> None:
        """
        Start all registered workers and run until stopped.
        """
        logger.info("Starting Xians Platform workers...")

        try:

            self._worker_host = WorkerHost(self.temporal_config)
            await self._worker_host.connect()

            self._temporal_client = self._worker_host.client

            await self._upload_definitions()

            task_queues = self._worker_registry.get_all_task_queues()

            if not task_queues:
                logger.warning("No workflows registered. Nothing to run.")
                return

            for task_queue in task_queues:
                workflows = self._worker_registry.get_workflows_for_queue(task_queue)
                activities = self._worker_registry.get_activities_for_queue(task_queue)
                worker_count = self._worker_registry.get_worker_count(task_queue)

                for workflow in workflows:
                    self._worker_host.register_workflow(workflow)
                for activity in activities:
                    self._worker_host.register_activity(activity)

                await self._worker_host.start_workers(
                    task_queues=[task_queue],
                    workflows=workflows,
                    activities=activities,
                    workers_per_queue=worker_count,
                )

            logger.info(f"Started workers for {len(task_queues)} task queues")

            await self._worker_host.run_until_stopped()

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
            raise

        except Exception as e:
            logger.error(f"Failed to run workers: {str(e)}", exc_info=True)
            raise TemporalError(
                f"Worker execution failed: {str(e)}",
                cause=e,
            )

        finally:
            logger.info("Cleaning up resources...")
            if self._worker_host:
                try:
                    await self._worker_host.shutdown()
                    logger.info("Workers shut down successfully")
                except Exception as cleanup_error:
                    logger.warning(f"Error during worker cleanup: {cleanup_error}")

            try:
                await self.xians_client.close()
                logger.info("Xians client closed successfully")
            except Exception as cleanup_error:
                logger.warning(f"Error closing Xians client: {cleanup_error}")

    async def _upload_definitions(self) -> None:
        """Upload agent and workflow definitions to Xians Server."""
        logger.info("Uploading definitions to Xians Server...")

        for agent_reg in self.agents.all():
            try:
                agent_key = await self.xians_client.upload_agent_definition(
                    agent_reg.definition
                )
                agent_reg.definition.agent_key = agent_key

                for workflow_def in agent_reg.workflows:
                    workflow_def.agent_key = agent_key
                    try:
                        await self.xians_client.upload_workflow_definition(workflow_def)
                        logger.debug(f"Uploaded workflow definition: {workflow_def.name}")
                    except Exception as wf_error:
                        logger.warning(
                            f"Failed to upload workflow definition for {workflow_def.name}: {wf_error}"
                        )

            except Exception as e:
                logger.warning(
                    f"Failed to upload definition for agent {agent_reg.definition.name}: {e}",
                    exc_info=True,
                )

        logger.info("Definitions uploaded successfully")

    def client(self) -> AgentClient:
        """
        Get an agent client for invoking workflows.
        """
        if not self._temporal_client:
            raise ConfigurationError(
                "Temporal client not initialized. Call run_all() first or connect manually."
            )

        return AgentClient(self._temporal_client)

    async def connect_temporal(self) -> None:
        """
        Connect to Temporal without starting workers.

        Useful for client-only mode (invoking workflows without hosting workers).
        """
        self._worker_host = WorkerHost(self.temporal_config)
        await self._worker_host.connect()
        self._temporal_client = self._worker_host.client
        logger.info("Connected to Temporal (client mode)")

    async def shutdown(self) -> None:
        """Shutdown platform and cleanup resources."""
        logger.info("Shutting down Xians Platform...")

        errors = []

        try:
            if self._worker_host:
                try:
                    await self._worker_host.shutdown()
                    logger.info("Workers shut down successfully")
                except Exception as e:
                    errors.append(f"Worker shutdown error: {e}")
                    logger.error(f"Error shutting down workers: {e}", exc_info=True)
        finally:
            try:
                await self.xians_client.close()
                logger.info("Xians client closed successfully")
            except Exception as e:
                errors.append(f"Xians client close error: {e}")
                logger.error(f"Error closing Xians client: {e}", exc_info=True)

        if errors:
            logger.warning(f"Shutdown completed with {len(errors)} error(s)")
        else:
            logger.info("Xians Platform shutdown complete")

    @staticmethod
    def _build_temporal_config_from_settings(settings: dict[str, object]) -> TemporalConfig:
        """Build TemporalConfig from server settings with .NET-aligned field names."""
        from urllib.parse import urlparse
        import os

        server_url_override = os.getenv("TEMPORAL_SERVER_URL")
        flow_server_url = str(server_url_override or settings.get("flowServerUrl") or "")
        if not flow_server_url:
            raise ConfigurationError("flowServerUrl missing from Temporal settings")

        parsed = urlparse(flow_server_url if "://" in flow_server_url else f"dns://{flow_server_url}")
        host = parsed.hostname or "localhost"
        port = parsed.port or 7233
        namespace = str(settings.get("flowServerNamespace") or settings.get("namespace") or "default")

        # TLS materials may be provided as base64 or raw PEM
        flow_server_cert_b64 = settings.get("flowServerCertBase64")
        flow_server_key_b64 = settings.get("flowServerPrivateKeyBase64")
        flow_server_ca_pem = settings.get("flowServerRootCaPem")
        flow_server_domain = settings.get("flowServerDomainOverride") or settings.get("flowServerSniDomain")

        tls_enabled = bool(flow_server_cert_b64 or flow_server_key_b64 or flow_server_ca_pem)

        # Build nested TLS config
        tls_cfg = None
        if tls_enabled:
            tls_cfg = TemporalTLSConfig(
                enabled=True,
                root_ca_pem=str(flow_server_ca_pem) if flow_server_ca_pem else None,
                client_cert_pem=str(flow_server_cert_b64) if flow_server_cert_b64 else None,
                client_key_pem=str(flow_server_key_b64) if flow_server_key_b64 else None,
                domain=str(flow_server_domain) if flow_server_domain else None,
                pem_is_base64=bool(flow_server_cert_b64 or flow_server_key_b64),
            )

        # Preserve legacy fields for backward compatibility (tests expect these)
        return TemporalConfig(
            address=f"{host}:{port}",
            namespace=namespace,
            task_queue=str(settings.get("task_queue") or "xians-agents"),
            tls=tls_cfg,
            host=host,
            port=port,
            tls_enabled=tls_enabled,
            server_root_ca_cert_base64=flow_server_cert_b64 if flow_server_ca_pem is None else None,
            client_cert_base64=flow_server_cert_b64,
            client_private_key_base64=flow_server_key_b64,
        )


__all__ = [
    "XiansPlatform",
    "AgentRegistry",
    "AgentRegistration",
]

