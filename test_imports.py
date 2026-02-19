#!/usr/bin/env python3
"""Test imports for xians library."""

try:
    from xians.platform.v1 import (
        XiansPlatform,
        XiansOptions,
        TemporalConfig,
        LLMConfig,
        AgentRequest,
        AgentResponse,
    )
    print("✅ Success! All imports working correctly")
    print(f"  - XiansPlatform: {XiansPlatform}")
    print(f"  - XiansOptions: {XiansOptions}")
    print(f"  - TemporalConfig: {TemporalConfig}")
    print(f"  - LLMConfig: {LLMConfig}")
    print(f"  - AgentRequest: {AgentRequest}")
    print(f"  - AgentResponse: {AgentResponse}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

