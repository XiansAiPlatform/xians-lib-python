"""
Example: Using standardized logging and exception handling in Xians SDK.

This example demonstrates:
1. Configuring logging (standard and structured)
2. Using exception handling decorators
3. Using exception context managers
4. Try-catch-finally patterns in agent code
"""

import asyncio
import logging

from temporalio import activity

from src.configs.v1.logging import LoggerMixin, configure_logging, get_logger, log_context
from src.middleware.v1 import (
    ExceptionHandlingContext,
    initialize_middleware,
    with_exception_handling,
)
from src.models.v1.entities import AgentRequest, AgentResponse
from src.platform.v1 import LLMConfig, TemporalConfig, XiansOptions, XiansPlatform

# Configure logging at application startup
configure_logging(
    log_level="INFO",
    enable_structured=False,  # Set to True if structlog is installed
)

logger = get_logger(__name__)


# Example 1: Using LoggerMixin in a class
class MyAgentService(LoggerMixin):
    """Example service class with built-in logger."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def call_external_api(self, query: str) -> dict:
        """Call external API with logging."""
        self.logger.info(
            "Calling external API",
            extra=log_context(query_length=len(query)),
        )

        try:
            # Simulate API call
            result = {"response": f"Result for: {query}"}
            self.logger.info("API call successful")
            return result

        except Exception as e:
            self.logger.error(
                "API call failed",
                extra=log_context(error=str(e)),
                exc_info=True,
            )
            raise


# Example 2: Using @with_exception_handling decorator (via middleware)
@with_exception_handling(
    operation_name="initialize_agent_components",
    re_raise=False,
)
async def initialize_agent_components() -> dict:
    """Initialize agent components with automatic error handling via middleware."""
    logger.info("Initializing agent components...")

    # If this fails, decorator will log and return None
    components = {
        "llm": "initialized",
        "vector_store": "initialized",
        "memory": "initialized",
    }

    logger.info("Agent components initialized successfully")
    return components


# Example 3: Using ExceptionHandlingContext for try-catch-finally (via middleware)
async def process_with_cleanup(data: str) -> str:
    """Process data with guaranteed cleanup using middleware context manager."""

    # Cleanup function that runs in finally block
    def cleanup():
        logger.info("Cleaning up resources")
        # Close connections, release locks, etc.

    async with ExceptionHandlingContext(
        operation_name="data_processing",
        cleanup_func=cleanup,
        re_raise=True,
    ):
        logger.info("Processing data", extra=log_context(data_size=len(data)))

        # Your processing logic here
        result = data.upper()

        logger.info("Processing complete")
        return result


# Example 4: Agent activity with comprehensive error handling
@activity.defn
async def execute_agent_with_logging(request: AgentRequest) -> AgentResponse:
    """
    Agent activity with proper logging and exception handling.

    Demonstrates best practices for production agents.
    """
    logger.info(
        "Starting agent execution",
        extra=log_context(
            agent_key=request.agent_key,
            conversation_id=request.conversation_id,
            message_length=len(str(request.message)),
        ),
    )

    agent_service = MyAgentService(api_key="secret")

    try:
        # Initialize components with error handling
        components = await initialize_agent_components()

        if components is None:
            logger.warning("Failed to initialize components, using defaults")
            components = {}

        # Process with cleanup guarantee
        message = request.message if isinstance(request.message, str) else str(request.message)

        async with ExceptionHandlingContext(
            operation_name="agent_processing",
            cleanup_func=lambda: logger.info("Agent processing cleanup"),
            re_raise=False,
        ):
            # Call external API - errors handled by middleware context
            try:
                api_result = await agent_service.call_external_api(message)
            except Exception as e:
                logger.warning(f"API call failed, using fallback: {e}")
                api_result = {"response": "fallback response"}

            response_text = api_result.get("response", "No response")

            logger.info(
                "Agent execution successful",
                extra=log_context(
                    response_length=len(response_text),
                    agent_key=request.agent_key,
                ),
            )

            return AgentResponse(
                text=response_text,
                metadata={
                    "components": list(components.keys()),
                    "api_called": True,
                },
            )

    except Exception as e:
        logger.error(
            "Agent execution failed",
            extra=log_context(
                agent_key=request.agent_key,
                error_type=type(e).__name__,
                error_message=str(e),
            ),
            exc_info=True,
        )

        # Return error response instead of raising
        return AgentResponse(
            text=f"Agent execution failed: {str(e)}",
            metadata={
                "error": True,
                "error_type": type(e).__name__,
            },
        )

    finally:
        logger.debug(
            "Agent execution completed (finally block)",
            extra=log_context(agent_key=request.agent_key),
        )


# Example 5: Platform initialization with logging
async def main() -> None:
    """Main application entry point."""
    logger.info("Starting Xians agent application")

    # Initialize exception handling middleware
    initialize_middleware()

    try:
        # Initialize platform (logging already configured inside)
        platform = await XiansPlatform.initialize(
            XiansOptions(
                server_url="https://api.xians.ai",
                api_key="your-api-key",
                temporal=TemporalConfig(
                    host="localhost",
                    port=7233,
                    namespace="default",
                ),
                llm=LLMConfig(
                    provider="openai",
                    model="gpt-4",
                    api_key="your-openai-key",
                ),
                log_level="INFO",  # This configures logging
                enable_structured_logging=False,
            )
        )

        # Register agent
        agent = platform.agents.register(
            name="LoggingExampleAgent",
            description="Agent with comprehensive logging",
        )

        # Define workflow
        agent.define_invoke_workflow(
            name="InvokeAgent",
            workers=2,
            activity_func=execute_agent_with_logging,
        )

        logger.info("Agent registered successfully, starting workers...")

        # Run workers (has try-catch-finally built-in)
        await platform.run_all()

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")

    except Exception as e:
        logger.critical(
            "Application failed",
            extra=log_context(error_type=type(e).__name__),
            exc_info=True,
        )
        raise

    finally:
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

