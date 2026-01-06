"""Main platform facade for Xians SDK v1."""

import logging
from typing import Callable

from temporalio.client import Client

from ...exceptions.v1.errors import ConfigurationError, TemporalError
from ...models.v1.configs import TemporalConfig, XiansOptions, XiansServerConfig
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

        Args:
            platform: Parent platform instance.
            definition: Agent definition.
        """
        self.platform = platform
        self.definition = definition
        self.workflows: list[WorkflowDefinition] = []

    def define_invoke_workflow(
        self,
        name: str = "InvokeAgent",
        workers: int = 1,
        activity_func: Callable | None = None,
    ) -> WorkflowDefinition:
        """
        Define an invoke (one-shot) workflow for this agent.

        Args:
            name: Workflow name.
            workers: Number of workers.
            activity_func: Activity function to execute the agent.

        Returns:
            The workflow definition.
        """
        from ...constants.v1.core import WorkflowType

        workflow_def = WorkflowDefinition(
            workflow_type=WorkflowType.TASK_BASED,
            name=name,
            workers=workers,
            agent_key=self.definition.agent_key or self.definition.name,
            activity_name=activity_func.__name__ if activity_func else "execute_agent_activity",
        )

        self.workflows.append(workflow_def)

        # Register with worker registry
        if activity_func:
            self.platform._worker_registry.register(
                agent_key=workflow_def.agent_key,
                workflow_name=workflow_def.name,
                workflow_class=InvokeAgentWorkflow,
                activity_func=activity_func,
                system_scoped=self.definition.system_scoped,
                workers=workers,
            )

        logger.info(f"Defined invoke workflow '{name}' for agent '{self.definition.name}'")
        return workflow_def

    def define_conversation_workflow(
        self,
        name: str = "Conversation",
        workers: int = 1,
        activity_func: Callable | None = None,
    ) -> WorkflowDefinition:
        """
        Define a conversational (long-running) workflow for this agent.

        Args:
            name: Workflow name.
            workers: Number of workers.
            activity_func: Activity function to execute the agent.

        Returns:
            The workflow definition.
        """
        from ...constants.v1.core import WorkflowType

        workflow_def = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name=name,
            workers=workers,
            agent_key=self.definition.agent_key or self.definition.name,
            activity_name=activity_func.__name__ if activity_func else "execute_agent_activity",
        )

        self.workflows.append(workflow_def)

        # Register with worker registry
        if activity_func:
            self.platform._worker_registry.register(
                agent_key=workflow_def.agent_key,
                workflow_name=workflow_def.name,
                workflow_class=ConversationWorkflow,
                activity_func=activity_func,
                system_scoped=self.definition.system_scoped,
                workers=workers,
            )

        logger.info(
            f"Defined conversation workflow '{name}' for agent '{self.definition.name}'"
        )
        return workflow_def


class AgentRegistry:
    """
    Registry for managing agent definitions and workflows.
    """

    def __init__(self, platform: "XiansPlatform") -> None:
        """
        Initialize agent registry.

        Args:
            platform: Parent platform instance.
        """
        self.platform = platform
        self._agents: dict[str, AgentRegistration] = {}

    def register(
        self,
        name: str,
        description: str | None = None,
        system_scoped: bool = False,
    ) -> AgentRegistration:
        """
        Register a new agent.

        Args:
            name: Agent name.
            description: Optional agent description.
            system_scoped: Whether agent is system-scoped.

        Returns:
            Agent registration for workflow configuration.
        """
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
        """Get an agent registration by name."""
        return self._agents.get(name)

    def all(self) -> list[AgentRegistration]:
        """Get all registered agents."""
        return list(self._agents.values())


class XiansPlatform:
    """
    Main entry point for Xians SDK.

    Provides:
    - Platform initialization and configuration
    - Agent registration
    - Workflow definition
    - Worker management
    - Client access for workflow invocation
    """

    def __init__(
        self,
        options: XiansOptions,
        xians_client: XiansServerClient,
        temporal_config: TemporalConfig,
    ) -> None:
        """
        Initialize platform (use XiansPlatform.initialize() instead).

        Args:
            options: Platform options.
            xians_client: Xians server client.
            temporal_config: Temporal configuration.
        """
        self.options = options
        self.xians_client = xians_client
        self.temporal_config = temporal_config

        self._worker_host: WorkerHost | None = None
        self._worker_registry = WorkerRegistry()
        self._temporal_client: Client | None = None

        # Public registries
        self.agents = AgentRegistry(self)

    @classmethod
    async def initialize(cls, options: XiansOptions) -> "XiansPlatform":
        """
        Initialize the Xians platform.

        Args:
            options: Platform configuration options.

        Returns:
            Initialized platform instance.

        Raises:
            ConfigurationError: If initialization fails.
        """
        logger.info("Initializing Xians Platform...")

        # Create Xians server client
        server_config = XiansServerConfig(
            server_url=options.server_url,
            api_key=options.api_key,
        )
        xians_client = XiansServerClient(server_config)

        # Fetch Temporal settings if not provided
        temporal_config = options.temporal
        if temporal_config is None:
            logger.info("Fetching Temporal settings from Xians Server...")
            try:
                settings = await xians_client.fetch_temporal_settings()
                temporal_config = TemporalConfig(
                    host=settings.get("host", "localhost"),
                    port=settings.get("port", 7233),
                    namespace=settings.get("namespace", "default"),
                    task_queue=settings.get("task_queue", "xians-agents"),
                )
                logger.info(f"Using Temporal at {temporal_config.host}:{temporal_config.port}")
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

        This will:
        1. Connect to Temporal
        2. Upload agent/workflow definitions to Xians Server
        3. Start workers for all registered workflows
        4. Run until interrupted

        Raises:
            TemporalError: If worker startup fails.
        """
        logger.info("Starting Xians Platform workers...")

        # Initialize worker host
        self._worker_host = WorkerHost(self.temporal_config)
        await self._worker_host.connect()

        # Store client reference
        self._temporal_client = self._worker_host.client

        # Upload definitions to Xians Server
        await self._upload_definitions()

        # Start workers for all registered task queues
        task_queues = self._worker_registry.get_all_task_queues()

        if not task_queues:
            logger.warning("No workflows registered. Nothing to run.")
            return

        for task_queue in task_queues:
            workflows = self._worker_registry.get_workflows_for_queue(task_queue)
            activities = self._worker_registry.get_activities_for_queue(task_queue)
            worker_count = self._worker_registry.get_worker_count(task_queue)

            # Register workflows and activities
            for workflow in workflows:
                self._worker_host.register_workflow(workflow)
            for activity in activities:
                self._worker_host.register_activity(activity)

            # Start workers
            await self._worker_host.start_workers(
                task_queues=[task_queue],
                workflows=workflows,
                activities=activities,
                workers_per_queue=worker_count,
            )

        logger.info(f"Started workers for {len(task_queues)} task queues")

        # Run until stopped
        await self._worker_host.run_until_stopped()

    async def _upload_definitions(self) -> None:
        """Upload agent and workflow definitions to Xians Server."""
        logger.info("Uploading definitions to Xians Server...")

        for agent_reg in self.agents.all():
            try:
                agent_key = await self.xians_client.upload_agent_definition(
                    agent_reg.definition
                )
                agent_reg.definition.agent_key = agent_key

                # Upload workflow definitions
                for workflow_def in agent_reg.workflows:
                    workflow_def.agent_key = agent_key
                    await self.xians_client.upload_workflow_definition(workflow_def)

            except Exception as e:
                logger.warning(
                    f"Failed to upload definition for agent {agent_reg.definition.name}: {e}"
                )

        logger.info("Definitions uploaded successfully")

    def client(self) -> AgentClient:
        """
        Get an agent client for invoking workflows.

        Returns:
            Agent client instance.

        Raises:
            ConfigurationError: If Temporal client is not initialized.
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

        if self._worker_host:
            await self._worker_host.shutdown()

        await self.xians_client.close()

        logger.info("Xians Platform shutdown complete")


__all__ = [
    "XiansPlatform",
    "AgentRegistry",
    "AgentRegistration",
]

