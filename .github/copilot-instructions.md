## Goals

1. **Temporal-native agent runtime**
   - Support long-running, durable agent workflows on Temporal.
   - Support both:
     - **Built-in workflow path** (library-owned workflow type + user handler callbacks)
     - **Custom workflow path** (user-authored workflow classes)

2. **Xians server integration**
   - Fetch FlowServer/Temporal settings from Xians server.
   - Upload agent/workflow definitions (hash-based idempotency).
   - Provide client APIs for:
     - Knowledge
     - Documents
     - Conversation / outbound messages
     - Usage events (optional but recommended)

3. **LLM framework-agnostic**
   - Do **NOT** couple to Semantic Kernel, LangChain, etc.
   - Provide a minimal LLM interface and first-party adapters.
   - Allow users to select providers/models and configure model parameters via SDK config.

4. **Enterprise-grade SDK**
   - Typed configs and models
   - Clear public API surface
   - Logging, resilience, retries
   - Test coverage and local dev tooling

---

## Current repository structure (do not break it)

Current structure under `src/xians/` (the single top-level package):

- `agents/` (core, scheduling, messaging, metrics, knowledge, documents)
- `configs/v1/`
- `constants/v1/`
- `exceptions/v1/`
- `interfaces/v1/`
- `logging/`
- `middleware/v1/`
- `models/v1/`
- `platform/v1/`
- `temporal_workflows/v1/`
- `utils/v1/`

**Preserve this structure**, but expand within it. Add new modules/subpackages as needed under these packages.

> LLM provider adapters are intentionally **NOT** part of this SDK — this
> mirrors `XiansAi.Lib` (.NET). Users bring their own LLM framework inside
> their Temporal activities. Do not reintroduce an `llm_adapters/` package.

---

## Technology choices (mandatory)

- Temporal: use **`temporalio`** (Temporal Python SDK).
- HTTP client: use **`httpx`** with retries (either `tenacity` or custom retry policy).
- Config + validation: prefer **Pydantic v2** (or dataclasses + validation if pydantic isn’t available).
- Logging: standard `logging` with structured option (optional `structlog`).
- Tests: `pytest` + `pytest-asyncio`.

---

## Public API: what users should be able to do

### A) Platform-style usage (parity with .NET `Xians.Lib`)

Target invocation:

```python
from xians.platform.v1 import XiansPlatform, XiansOptions

platform = await XiansPlatform.initialize(
    XiansOptions(server_url="...", api_key="...", temporal=None, llm=...)
)

agent = platform.agents.register(name="My Agent", system_scoped=False)

wf = agent.workflows.define_builtin("Conversational", workers=2)

@wf.on_user_chat_message
async def handle_chat(ctx):
    # user can call LLM through ctx.llm or platform.llm
    resp = await ctx.llm.chat(
        messages=[{"role": "user", "content": ctx.message.text}],
        model=ctx.config.llm.model,  # override allowed
    )
    await ctx.reply(resp.text)

await agent.run_all()
