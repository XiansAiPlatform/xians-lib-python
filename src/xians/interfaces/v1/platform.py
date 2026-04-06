"""Main platform facade for Xians SDK v1.

Aligned with C# XiansPlatform, AgentCollection, XiansWorkflow.
Supports agent registration, workflow definition, handler registration,
definition upload with hash check, and Temporal worker startup.
"""

import inspect
import logging
import os
from typing import Any, Callable, Optional

from temporalio.client import Client

from ...agents.core.xians_context import XiansContext
from ...agents.documents import DocumentCollection
from ...agents.documents.document_activities import DocumentActivities
from ...agents.knowledge import KnowledgeCollection
from ...agents.knowledge.providers.factory import KnowledgeProviderFactory
from ...agents.messaging.message_service import MessageService
from ...agents.metrics import MetricsCollection
from ...agents.metrics.usage_activities import UsageActivities
from ...configs.v1.logging import configure_logging
from ...exceptions.v1.errors import ConfigurationError, TemporalError
from ...logging.logging_services import LoggingServices
from ...logging.xians_logger import install_api_handler_on_root
from ...middleware.v1 import initialize_middleware
from ...models.v1.configs import (
    CertificateInfo,
    TemporalConfig,
    TemporalTLSConfig,
    XiansOptions,
    XiansServerConfig,
)
from ...models.v1.entities import XiansAgentRegistration
from ...temporal_workflows.v1.message_activities import MessageActivities
from ...temporal_workflows.v1.models import WorkflowOptions
from ...temporal_workflows.v1.worker_runner import (
    WorkerHost,
    WorkerRegistry,
    build_task_queue_name,
)
from ...temporal_workflows.v1.workflows import BuiltinWorkflow, create_named_builtin_workflow
from ...utils.v1.hashing import compute_definition_hash
from ..v1.agent_client import AgentClient
from ..v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class XiansWorkflow:
    """Represents a defined workflow for an agent. Matches C# XiansWorkflow.

    Supports handler registration for chat, data, file, and webhook messages.
    """

    def __init__(
        self,
        agent_name: str,
        workflow_type: str,
        workflow_name: str,
        workers: int,
        system_scoped: bool,
        tenant_id: Optional[str],
        max_history_length: int = 1000,
        inactivity_timeout: Optional[float] = None,
    ):
        self.agent_name = agent_name
        self.workflow_type = workflow_type
        self.workflow_name = workflow_name
        self.workers = workers
        self.system_scoped = system_scoped
        self.tenant_id = None if system_scoped else tenant_id
        self.max_history_length = max_history_length
        self.inactivity_timeout = inactivity_timeout
        self._activity_instances: list = []
        self._custom_workflow_class: Optional[type] = None
        self._parameter_definitions: list[dict[str, Any]] = []

        BuiltinWorkflow.register_workflow_options(
            workflow_type,
            WorkflowOptions(
                max_history_length=max_history_length,
                inactivity_timeout=inactivity_timeout,
            ),
        )

        XiansContext.register_workflow(workflow_type, self)

    def set_parameter_definitions(self, parameter_definitions: list[dict[str, Any]]) -> "XiansWorkflow":
        """Set top-level parameter definitions for this workflow definition.

        C# uploads `parameterDefinitions` based on the WorkflowRun method signature for
        custom workflows, and uploads an empty list for built-in workflows.
        """
        self._parameter_definitions = parameter_definitions or []
        return self

    def _infer_parameter_definitions_from_custom_workflow(self) -> list[dict[str, Any]]:
        """Infer parameterDefinitions from a custom workflow class (best-effort)."""
        wf_cls = self._custom_workflow_class
        if wf_cls is None:
            return []

        run_fn = getattr(wf_cls, "run", None)
        if run_fn is None:
            return []

        try:
            sig = inspect.signature(run_fn)
        except (TypeError, ValueError):
            return []

        defs: list[dict[str, Any]] = []
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            ann = param.annotation
            if ann is inspect._empty:
                type_name = "Any"
            else:
                type_name = getattr(ann, "__name__", str(ann))

            defs.append(
                {
                    "name": name,
                    "type": type_name,
                    "optional": param.default is not inspect._empty,
                }
            )
        return defs

    def on_user_chat_message(self, handler: Callable) -> None:
        """Register a chat message handler. Matches C# XiansWorkflow.OnUserChatMessage."""
        BuiltinWorkflow.register_chat_handler(
            workflow_type=self.workflow_type,
            handler=handler,
            agent_name=self.agent_name,
            tenant_id=self.tenant_id,
            system_scoped=self.system_scoped,
        )

    def on_user_data_message(self, handler: Callable) -> None:
        """Register a data message handler."""
        BuiltinWorkflow.register_data_handler(
            workflow_type=self.workflow_type,
            handler=handler,
            agent_name=self.agent_name,
            tenant_id=self.tenant_id,
            system_scoped=self.system_scoped,
        )

    def on_file_upload(self, handler: Callable) -> None:
        """Register a file upload handler."""
        BuiltinWorkflow.register_file_upload_handler(
            workflow_type=self.workflow_type,
            handler=handler,
            agent_name=self.agent_name,
            tenant_id=self.tenant_id,
            system_scoped=self.system_scoped,
        )

    def on_webhook(self, handler: Callable) -> None:
        """Register a webhook handler."""
        BuiltinWorkflow.register_webhook_handler(
            workflow_type=self.workflow_type,
            handler=handler,
            agent_name=self.agent_name,
            tenant_id=self.tenant_id,
            system_scoped=self.system_scoped,
        )

    def add_activity(self, activity_instance: object) -> "XiansWorkflow":
        """Add a custom activity instance to this workflow's worker."""
        self._activity_instances.append(activity_instance)
        return self

    def build_definition(self) -> dict:
        """Build the workflow definition dict for upload.

        Produces the exact shape the server's FlowDefinitionRequest expects,
        including the required activityDefinitions and parameterDefinitions.
        """
        parameter_definitions = (
            self._parameter_definitions
            if self._parameter_definitions
            else self._infer_parameter_definitions_from_custom_workflow()
        )

        return {
            "agent": self.agent_name,
            "workflowType": self.workflow_type,
            "name": self.workflow_name,
            "systemScoped": self.system_scoped,
            "workers": self.workers,
            "activable": True,
            "activityDefinitions": [
                {
                    "activityName": "ProcessAndSendMessage",
                    "knowledgeIds": [],
                    "parameterDefinitions": [],
                }
            ],
            "parameterDefinitions": parameter_definitions,
        }


class AgentRegistration:
    """Registered agent with workflow definition capabilities.

    Matches C# XiansAgent.
    """

    def __init__(
        self,
        registration: XiansAgentRegistration,
        tenant_id: str,
        platform: "XiansPlatform",
    ):
        self._registration = registration
        self._tenant_id = tenant_id
        self._platform = platform
        self._workflows: list[XiansWorkflow] = []
        self._knowledge: Optional[KnowledgeCollection] = None
        self._metrics: Optional[MetricsCollection] = None
        self._documents: Optional[DocumentCollection] = None

        XiansContext.register_agent(registration.name, self)

    @property
    def name(self) -> str:
        return self._registration.name

    @property
    def system_scoped(self) -> bool:
        return self._registration.is_template

    @property
    def http_client(self):
        """Access the underlying httpx.AsyncClient for HTTP operations.

        Mirrors C# XiansAgent.HttpService.Client. Used internally by
        UserMessaging and other components that need direct HTTP access
        from within activity context.
        """
        return self._platform.xians_client._client

    @property
    def knowledge(self) -> KnowledgeCollection:
        """Access the agent's knowledge collection (lazy-initialized).

        Mirrors C# ``XiansAgent.Knowledge``, accessible as
        ``XiansContext.CurrentAgent.knowledge``.
        """
        if self._knowledge is None:
            provider = KnowledgeProviderFactory.create(
                local_mode=self._platform.options.local_mode,
                http_client=self._platform.xians_client._client,
            )
            self._knowledge = KnowledgeCollection(
                agent_name=self.name,
                provider=provider,
                tenant_id=self._tenant_id or None,
                system_scoped=self.system_scoped,
            )
        return self._knowledge

    @property
    def metrics(self) -> MetricsCollection:
        """Access the agent's metrics collection (lazy-initialized).

        Mirrors C# XiansAgent.Metrics, accessible as
        XiansContext.CurrentAgent.metrics.
        """
        if self._metrics is None:
            self._metrics = MetricsCollection(
                agent_name=self.name,
                http_client=self._platform.xians_client,
                platform=self._platform,
            )
        return self._metrics

    @property
    def documents(self) -> DocumentCollection:
        """Access the agent's document collection (lazy-initialized).

        Mirrors C# XiansAgent.Documents, accessible as
        XiansContext.CurrentAgent.documents.
        """
        if self._documents is None:
            self._documents = DocumentCollection(
                agent_name=self.name,
                http_client=self._platform.xians_client,
                tenant_id=self._tenant_id or "",
                system_scoped=self.system_scoped,
            )
        return self._documents

    def define_builtin_workflow(
        self,
        name: str,
        workers: int = 1,
        max_history_length: int = 1000,
        inactivity_timeout: Optional[float] = None,
    ) -> XiansWorkflow:
        """Define a built-in conversational workflow.

        Matches C#: xiansAgent.Workflows.DefineBuiltIn(name)
        """
        workflow_type = f"{self.name}:{name}"
        wf = XiansWorkflow(
            agent_name=self.name,
            workflow_type=workflow_type,
            workflow_name=name,
            workers=workers,
            system_scoped=self.system_scoped,
            tenant_id=self._tenant_id,
            max_history_length=max_history_length,
            inactivity_timeout=inactivity_timeout,
        )
        self._workflows.append(wf)
        return wf

    def define_custom_workflow(
        self,
        workflow_class: type,
        workers: int = 1,
    ) -> XiansWorkflow:
        """Define a custom workflow class. Matches C# DefineCustom<T>()."""
        wf_defn = getattr(workflow_class, "__temporal_workflow_definition", None)
        workflow_type = wf_defn.name if wf_defn else None

        if not workflow_type:
            raise ConfigurationError(
                f"Custom workflow class {workflow_class.__name__} must use "
                f"@workflow.defn(name='{self.name}:WorkflowName')"
            )

        if not workflow_type.startswith(f"{self.name}:"):
            raise ConfigurationError(
                f"Custom workflow type '{workflow_type}' must start with '{self.name}:'"
            )

        workflow_name = workflow_type.split(":", 1)[1]
        wf = XiansWorkflow(
            agent_name=self.name,
            workflow_type=workflow_type,
            workflow_name=workflow_name,
            workers=workers,
            system_scoped=self.system_scoped,
            tenant_id=self._tenant_id,
        )
        wf._custom_workflow_class = workflow_class
        self._workflows.append(wf)
        return wf

    async def run_all_async(self) -> None:
        """Upload definitions and start all workers.

        Matches C#: xiansAgent.RunAllAsync()
        """
        await self._platform.run_all()


class AgentRegistry:
    """Registry for managing agent definitions. Matches C# AgentCollection."""

    def __init__(self, platform: "XiansPlatform") -> None:
        self._platform = platform
        self._agents: dict[str, AgentRegistration] = {}

    def register(
        self,
        registration: XiansAgentRegistration | None = None,
        *,
        name: str = "",
        description: Optional[str] = None,
        system_scoped: bool = False,
        is_template: bool = False,
        summary: Optional[str] = None,
        version: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
    ) -> AgentRegistration:
        """Register an agent.

        Accepts either a XiansAgentRegistration object or keyword arguments.
        """
        if registration is None:
            registration = XiansAgentRegistration(
                name=name,
                is_template=is_template or system_scoped,
                description=description,
                summary=summary,
                version=version,
                author=author,
                category=category,
            )

        tenant_id = self._platform._tenant_id or ""
        agent_reg = AgentRegistration(registration, tenant_id, self._platform)
        self._agents[registration.name] = agent_reg

        logger.info(f"Registered agent: {registration.name} (system_scoped={registration.system_scoped})")
        return agent_reg

    def get(self, name: str) -> AgentRegistration | None:
        return self._agents.get(name)

    def all(self) -> list[AgentRegistration]:
        return list(self._agents.values())


class XiansPlatform:
    """Main entry point for Xians SDK. Matches C# XiansPlatform.

    Usage:
        platform = await XiansPlatform.initialize(XiansOptions(...))
        agent = platform.agents.register(XiansAgentRegistration(name="My Agent"))
        workflow = agent.define_builtin_workflow(name="Conversational")
        workflow.on_user_chat_message(my_handler)
        await agent.run_all_async()
    """

    def __init__(
        self,
        options: XiansOptions,
        xians_client: XiansServerClient,
        temporal_config: TemporalConfig | None,
    ) -> None:
        self.options = options
        self.xians_client = xians_client
        self.temporal_config = temporal_config

        self._worker_host: WorkerHost | None = None
        self._worker_registry = WorkerRegistry()
        self._temporal_client: Client | None = None
        self._tenant_id: str = ""
        self._message_service: MessageService | None = None

        self.agents = AgentRegistry(self)

    @classmethod
    async def initialize(cls, options: XiansOptions) -> "XiansPlatform":
        """Initialize the Xians platform.

        Sequence (matching C#):
        1. Validate options
        2. Parse certificate from ApiKey
        3. Configure logging
        4. Create HTTP client service
        5. Fetch Temporal configuration from server (if not provided)
        6. Create platform instance
        7. Display initialization banner
        """
        initialize_middleware()

        if not options.server_url:
            raise ConfigurationError("server_url is required")
        if not options.api_key:
            raise ConfigurationError("api_key is required")

        cert_info = options.certificate_info

        log_level = options.console_log_level or options.log_level or "INFO"
        configure_logging(
            log_level=log_level,
            enable_structured=options.enable_structured_logging,
        )

        server_config = XiansServerConfig(
            server_url=str(options.server_url),
            api_key=options.api_key,
            tenant_id=cert_info.tenant_id,
        )
        xians_client = XiansServerClient(server_config)

        # Initialize server logging (matches C# LoggingServices.Initialize)
        server_log_level_str = (
            options.server_log_level
            or os.environ.get("SERVER_LOG_LEVEL")
            or os.environ.get("API_LOG_LEVEL")
        )
        if server_log_level_str:
            import logging as _logging
            _level_map = {
                "TRACE": _logging.DEBUG,
                "DEBUG": _logging.DEBUG,
                "INFO": _logging.INFO,
                "INFORMATION": _logging.INFO,
                "WARNING": _logging.WARNING,
                "WARN": _logging.WARNING,
                "ERROR": _logging.ERROR,
                "CRITICAL": _logging.CRITICAL,
            }
            server_log_level = _level_map.get(
                server_log_level_str.strip().upper(), _logging.WARNING
            )

            logging_svc = LoggingServices.get_instance()
            logging_svc.initialize(
                http_client=xians_client._client,
                server_log_level=server_log_level,
            )
            install_api_handler_on_root()
            logger.info(
                f"Server logging enabled (level: {server_log_level_str.upper()})"
            )

        temporal_config = options.temporal
        if temporal_config is None and not options.local_mode:
            logger.info("Fetching Temporal settings from Xians Server...")
            try:
                settings = await xians_client.fetch_temporal_settings()
                temporal_config = cls._build_temporal_config_from_settings(settings)
                logger.info(f"Using Temporal at {temporal_config.address}")
            except Exception as e:
                raise ConfigurationError(
                    "Failed to fetch Temporal settings from Xians Server",
                    cause=e,
                )

        platform = cls(options, xians_client, temporal_config)
        platform._tenant_id = cert_info.tenant_id

        cls._display_banner(options, cert_info)

        logger.info("Xians Platform initialized successfully")
        return platform

    async def run_all(self) -> None:
        """Start all registered workers and run until stopped."""
        logger.info("Starting Xians Platform workers...")

        try:
            if self.temporal_config:
                self._worker_host = WorkerHost(self.temporal_config)
                await self._worker_host.connect()
                self._temporal_client = self._worker_host.client

            self._message_service = MessageService(self.xians_client._client)

            await self._upload_definitions()

            await self._register_and_start_workers()

            if self._worker_host:
                await self._worker_host.run_until_stopped()

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
            raise

        except Exception as e:
            logger.error(f"Failed to run workers: {str(e)}", exc_info=True)
            raise TemporalError(f"Worker execution failed: {str(e)}", cause=e)

        finally:
            logger.info("Cleaning up resources...")
            try:
                logging_svc = LoggingServices.get_instance()
                if logging_svc.is_initialized:
                    logging_svc.shutdown()
            except Exception as cleanup_error:
                logger.warning(f"Error flushing logs: {cleanup_error}")
            if self._worker_host:
                try:
                    await self._worker_host.shutdown()
                except Exception as cleanup_error:
                    logger.warning(f"Error during worker cleanup: {cleanup_error}")
            try:
                await self.xians_client.close()
            except Exception as cleanup_error:
                logger.warning(f"Error closing Xians client: {cleanup_error}")

    async def _upload_definitions(self) -> None:
        """Upload agent and workflow definitions to the server.

        Sequence (matching C#):
        1. Upload agent definition
        2. For each workflow: hash check -> conditional upload
        """
        logger.info("Uploading definitions to Xians Server...")

        for agent_reg in self.agents.all():
            try:
                await self.xians_client.upload_agent_definition(
                    agent_name=agent_reg.name,
                    system_scoped=agent_reg.system_scoped,
                    description=agent_reg._registration.description,
                    summary=agent_reg._registration.summary,
                    version=agent_reg._registration.version,
                    author=agent_reg._registration.author,
                    category=agent_reg._registration.category,
                )

                for wf in agent_reg._workflows:
                    try:
                        definition = wf.build_definition()
                        definition_hash = compute_definition_hash(definition)

                        is_current = await self.xians_client.check_definition_hash(
                            workflow_type=wf.workflow_type,
                            system_scoped=wf.system_scoped,
                            hash_value=definition_hash,
                        )

                        if not is_current:
                            await self.xians_client.upload_flow_definition(definition)
                            logger.info(f"Uploaded workflow definition: {wf.workflow_type}")
                        else:
                            logger.debug(f"Workflow definition up-to-date: {wf.workflow_type}")

                    except Exception as wf_error:
                        logger.warning(f"Failed to upload workflow definition for {wf.workflow_type}: {wf_error}")

            except Exception as e:
                logger.warning(f"Failed to upload definition for agent {agent_reg.name}: {e}", exc_info=True)

        logger.info("Definitions uploaded successfully")

    async def _register_and_start_workers(self) -> None:
        """Register workflows and start Temporal workers."""
        if not self._worker_host or not self._temporal_client:
            logger.warning("No Temporal connection. Skipping worker startup.")
            return

        message_activities = MessageActivities(self._message_service)
        usage_activities = UsageActivities(self.xians_client)
        document_activities = DocumentActivities(self.xians_client)

        for agent_reg in self.agents.all():
            for wf in agent_reg._workflows:
                if wf._custom_workflow_class:
                    workflow_class = wf._custom_workflow_class
                else:
                    workflow_class = create_named_builtin_workflow(wf.workflow_type)

                activity_instances = [
                    message_activities,
                    usage_activities,
                    document_activities,
                ] + wf._activity_instances

                task_queue = build_task_queue_name(
                    workflow_type=wf.workflow_type,
                    system_scoped=wf.system_scoped,
                    tenant_id=wf.tenant_id,
                )

                all_activities = []
                for instance in activity_instances:
                    if callable(instance) and hasattr(instance, "__temporal_activity_definition"):
                        all_activities.append(instance)
                    else:
                        all_activities.extend(WorkerHost._get_activity_methods(instance))

                await self._worker_host.start_worker(
                    task_queue=task_queue,
                    workflows=[workflow_class],
                    activities=all_activities,
                    max_concurrent_activities=wf.workers * 10,
                )

                logger.info(f"Started worker for {wf.workflow_type} on queue {task_queue}")

    def client(self) -> AgentClient:
        """Get an agent client for invoking workflows."""
        if not self._temporal_client:
            raise ConfigurationError(
                "Temporal client not initialized. Call run_all() first or connect manually."
            )
        return AgentClient(self._temporal_client)

    async def connect_temporal(self) -> None:
        """Connect to Temporal without starting workers (client-only mode)."""
        if not self.temporal_config:
            raise ConfigurationError("No Temporal configuration available")
        self._worker_host = WorkerHost(self.temporal_config)
        await self._worker_host.connect()
        self._temporal_client = self._worker_host.client
        logger.info("Connected to Temporal (client mode)")

    async def shutdown(self) -> None:
        """Shutdown platform and cleanup resources."""
        logger.info("Shutting down Xians Platform...")

        errors = []

        # Flush server logs before tearing down the HTTP client
        try:
            logging_svc = LoggingServices.get_instance()
            if logging_svc.is_initialized:
                logging_svc.shutdown()
        except Exception as e:
            errors.append(f"LoggingServices shutdown error: {e}")

        try:
            if self._worker_host:
                try:
                    await self._worker_host.shutdown()
                except Exception as e:
                    errors.append(f"Worker shutdown error: {e}")
        finally:
            try:
                await self.xians_client.close()
            except Exception as e:
                errors.append(f"Xians client close error: {e}")

        if errors:
            logger.warning(f"Shutdown completed with {len(errors)} error(s)")
        else:
            logger.info("Xians Platform shutdown complete")

    @staticmethod
    def _display_banner(options: XiansOptions, cert_info: CertificateInfo) -> None:
        logger.info("=" * 60)
        logger.info("Xians Platform Initialized")
        logger.info(f"  Server URL:    {options.server_url}")
        logger.info(f"  Tenant ID:     {cert_info.tenant_id}")
        logger.info(f"  User ID:       {cert_info.user_id}")
        logger.info(f"  Certificate:   {cert_info.subject}")
        logger.info(f"  Thumbprint:    {cert_info.thumbprint}")
        logger.info(f"  Expires:       {cert_info.expires_at.isoformat()}")
        logger.info("=" * 60)

    @staticmethod
    def _build_temporal_config_from_settings(settings: dict[str, object]) -> TemporalConfig:
        """Build TemporalConfig from server settings."""
        server_url_override = os.getenv("TEMPORAL_SERVER_URL")
        flow_server_url = str(server_url_override or settings.get("flowServerUrl") or "")
        if not flow_server_url:
            raise ConfigurationError("flowServerUrl missing from Temporal settings")

        flow_server_url = flow_server_url.strip()
        if "://" in flow_server_url:
            _, flow_server_url = flow_server_url.split("://", 1)

        host: str
        port: int

        if ":" in flow_server_url:
            parts = flow_server_url.rsplit(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except (ValueError, IndexError):
                logger.warning(f"Invalid port in flowServerUrl '{flow_server_url}', using default 7233")
                port = 7233
        else:
            host = flow_server_url
            port = 7233

        host = host.strip().rstrip("/")
        if not host:
            raise ConfigurationError(
                f"Invalid flowServerUrl: '{settings.get('flowServerUrl')}' - could not extract hostname"
            )

        namespace = str(settings.get("flowServerNamespace") or settings.get("namespace") or "default")

        flow_server_cert_b64 = settings.get("flowServerCertBase64")
        flow_server_key_b64 = settings.get("flowServerPrivateKeyBase64")
        flow_server_ca_pem = settings.get("flowServerRootCaPem")
        flow_server_domain = settings.get("flowServerDomainOverride") or settings.get("flowServerSniDomain")

        tls_enabled = bool(flow_server_cert_b64 or flow_server_key_b64 or flow_server_ca_pem)

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
    "XiansWorkflow",
    "KnowledgeCollection",
    "DocumentCollection",
]
