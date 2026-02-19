"""
Client example for invoking the EchoAgent from basic_invoke_agent.py.

This demonstrates how to invoke an agent workflow from a client application.

Prerequisites:
1. Run basic_invoke_agent.py first to start the agent worker
2. Then run this script to invoke the agent

Usage:
    python examples/invoke_agent_client.py
"""

import asyncio
import uuid

from xians.platform.v1 import (
    XiansPlatform,
    XiansOptions,
    LLMConfig,
    AgentRequest,
)


async def main() -> None:
    """Invoke the EchoAgent from a client."""
    # Initialize platform in client mode (no workers)
    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url="https://api.agentri.ai",
            api_key="MIIESjCCAjKgAwIBAgIQSPOZKNbiT0mJT2wcodoT9zANBgkqhkiG9w0BAQsFADBdMQ4wDAYDVQQIDAVTdGF0ZTENMAsGA1UEBwwEQ2l0eTEVMBMGA1UECgwMT3JnYW5pemF0aW9uMQswCQYDVQQLDAJJVDEYMBYGA1UEAwwPQWdlbnRyaSBSb290IENBMB4XDTI2MDEwNzA1NDk0MFoXDTMxMDEwNzA1NTk0MFowNDEMMAoGA1UEChMDOTl4MRIwEAYDVQQLEwkyNTI1MzkwOTExEDAOBgNVBAMTB1hpYW5zQWkwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDilTzWNQ3DoOSmr6tzr0QlFzwH6h6u3nB2hzAphTil48HW0YYB+j2cjOPzVCYUNfO0Xa9RC/C74HBzsJuATQJuGRQiRH+0VwN/qlcuqSX0DtFHkMbujKhttLGZX9c1uBttNuBJSE/q3rN8Zr4cJynGMp0vVL07ZQ52OLTSsj0UEdotv+wLhfaPeLKcqI1w3s4lpIbGEl8m6VILow+BEcJMdTS28ZH2Ge1IAjvSC8c2RngZs2qYDzpUB1U9zZ/ntFA2EUVorQyN9XA1lUlG2x00uj3wEWsJ11BxKryPEV7P9PP+X5dVtw5J3WOqmBAm6yG+4q/4l1geJp3hxbrhm8HxAgMBAAGjLzAtMBMGA1UdJQQMMAoGCCsGAQUFBwMCMAkGA1UdEwQCMAAwCwYDVR0PBAQDAgWgMA0GCSqGSIb3DQEBCwUAA4ICAQAE+OA7hIfwymnI13m9Jl/m+iHtBVwqhy0biTi/Do4hnDedLBtLCBXpbOkGqkGW0D+HCLxAe7bLAzoIiNmCZ4NVexyMKUyQ4n8SoTor0j3fyEKmxdlv/K4ulsFKtcVfkecJj1MvI/Mh9ItkAqiF/tmPI04Kpnle2PycmPF3q7TNsN+itTIufW/Yet0esnfzd5Nx18Q1qpSv/9Jqu/u7YminjEIGHKYhWP/waHEOctp4WeBtVVfydhwIKR9PO+vivHPPWChwoKgWh0w4wR1nua25itPYpX0SnuH7OZsWQ2zmN+79dcVW/RL58zjqT6LcJ0IXZbsJ3F43Hl8tIwhwL8Fx1oF7OSLtxnKRI57dzfTa0F9elLJ3aKD04bBplyhqYYAUoNNq3ie7AsTrWCnttWfBay5gFM+7Lhg5bri50oqptTzL6ltBe5Be/D8r1pnF7blzTAwWxY5TtMzXVy6zsWV5dQY9P4znmJO5o32uFyVvu5W3DmpgDqhi7kCmVfj4P1yh9vN6cth+kvOQN6YumFYYClBxGa79sOlqwE8tUKfjlesrAsP1Ego2KFBGBkcNxCLw0T8u4bfYV9sZ6d9tbbcj6EwzarCkkPubvAU/xiZl85zJDqRPXdILxQb6rvvrxGTH+iID8J+KhtiwvHUnTDxfLkDppE9dM2UAhc5C7EChqw==",
            temporal=None,  # Will be fetched from Xians Server
            llm=LLMConfig(
                provider="google_vertex",
                model="gemini-2.5-flash",
                api_key="AIzaSyDDze7ut9iqtMK86qTa7yoGYIkg1TD9Cqw",
            ),
        )
    )

    # Connect to Temporal without starting workers
    await platform.connect_temporal()

    # Get the agent client
    client = platform.client()

    # Generate a unique workflow ID
    workflow_id = f"echo-{uuid.uuid4()}"

    # Task queue follows the pattern: xians-{scope}-{agent_key}-{workflow_name}
    # For user-scoped agent named "EchoAgent" with workflow "InvokeEcho":
    task_queue = "xians-default-user-EchoAgent-InvokeEcho"

    print(f"Invoking agent with workflow ID: {workflow_id}")
    print(f"Task queue: {task_queue}")

    # Create the request
    request = AgentRequest(
        agent_key="EchoAgent",
        message="Hello from the client!",
        conversation_id=str(uuid.uuid4()),
        metadata={"source": "client_example"},
    )

    try:
        # Invoke the agent workflow
        response = await client.invoke(
            workflow_id=workflow_id,
            task_queue=task_queue,
            request=request,
            workflow_type="InvokeAgentWorkflow",
        )

        print(f"\n✅ Agent Response:")
        print(f"   Text: {response.text}")
        if response.payload:
            print(f"   Payload: {response.payload}")
        if response.usage:
            print(f"   Usage: {response.usage}")

    except Exception as e:
        print(f"\n❌ Error invoking agent: {e}")
        raise

    finally:
        # Clean up
        await platform.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

