#!/usr/bin/env python3
"""
Test script to demonstrate the import structure issue.

This script tests different import patterns to show what works and what doesn't.
"""

import sys
from pathlib import Path

print("=" * 80)
print("XIANS-LIB-PYTHON IMPORT STRUCTURE TEST")
print("=" * 80)
print()

# Test 1: Without any path manipulation (simulates external usage after pip install)
print("Test 1: Import as external user would (no path manipulation)")
print("-" * 80)

sys_path_backup = sys.path.copy()

try:
    from xians.platform.v1 import XiansPlatform
    print("✅ SUCCESS: from platform.v1 import XiansPlatform")
except ImportError as e:
    print(f"❌ FAILED: from platform.v1 import XiansPlatform")
    print(f"   Error: {e}")
except Exception as e:
    print(f"❌ FAILED: from platform.v1 import XiansPlatform")
    print(f"   Unexpected error: {type(e).__name__}: {e}")

print()

# Test 2: With src/ in path (simulates development environment)
print("Test 2: With src/ in PYTHONPATH (development mode)")
print("-" * 80)

sys.path = sys_path_backup.copy()
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

print(f"Added to sys.path: {src_path}")

try:
    # Clear any previously imported modules
    if 'platform' in sys.modules:
        del sys.modules['platform']
    if 'platform.v1' in sys.modules:
        del sys.modules['platform.v1']

    from xians.platform.v1 import XiansPlatform
    print("✅ SUCCESS: from platform.v1 import XiansPlatform")
except ImportError as e:
    print(f"❌ FAILED: from platform.v1 import XiansPlatform")
    print(f"   Error: {e}")
    print(f"   This is the CRITICAL BUG - relative imports fail!")
except Exception as e:
    print(f"❌ FAILED: from platform.v1 import XiansPlatform")
    print(f"   Unexpected error: {type(e).__name__}: {e}")

print()

# Test 3: Try the intended import path (from xians.platform.v1)
print("Test 3: Intended import path (from xians.platform.v1)")
print("-" * 80)

sys.path = sys_path_backup.copy()
sys.path.insert(0, str(src_path))

try:
    from xians.platform.v1 import XiansPlatform
    print("✅ SUCCESS: from xians.platform.v1 import XiansPlatform")
except ModuleNotFoundError as e:
    print(f"❌ FAILED: from xians.platform.v1 import XiansPlatform")
    print(f"   Error: {e}")
    print(f"   Expected - no 'xians' namespace package exists")
except Exception as e:
    print(f"❌ FAILED: from xians.platform.v1 import XiansPlatform")
    print(f"   Unexpected error: {type(e).__name__}: {e}")

print()

# Test 4: Try importing submodules that don't have relative imports
print("Test 4: Import module without relative imports (if any)")
print("-" * 80)

sys.path = sys_path_backup.copy()
sys.path.insert(0, str(src_path))

try:
    from xians.constants import WorkflowType
    print("✅ SUCCESS: from constants.v1 import WorkflowType")
    print(f"   WorkflowType values: {[wt.value for wt in WorkflowType]}")
except Exception as e:
    print(f"❌ FAILED: from constants.v1 import WorkflowType")
    print(f"   Error: {type(e).__name__}: {e}")

print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("Current Status: ⚠️  PACKAGE CANNOT BE USED EXTERNALLY")
print()
print("Root Cause:")
print("  - Modules use relative imports (from ...models.v1)")
print("  - No parent 'xians' namespace package exists")
print("  - Setuptools exposes modules as top-level (platform, configs, etc.)")
print()
print("Solution:")
print("  1. Create src/xians/ directory")
print("  2. Move all modules under src/xians/")
print("  3. Change relative imports to: from xians.configs.v1 import ...")
print()
print("See docs/IMPORT_STRUCTURE_ISSUE.md for detailed analysis and solutions.")
print()

