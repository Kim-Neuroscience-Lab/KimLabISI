#!/usr/bin/env python3
"""
Architecture Verification - Complete Structure Validation

This script verifies that all directories and files match the documented
Clean Architecture structure exactly as specified in our ADRs.
"""

import os
from pathlib import Path
from typing import Dict, List, Set


def get_expected_architecture() -> Dict[str, List[str]]:
    """Return the expected Clean Architecture structure"""
    return {
        # Domain Layer - Pure business logic
        "src/domain": [
            "__init__.py"
        ],
        "src/domain/entities": [
            "__init__.py",
            "workflow_state.py"  # Our core 12-state workflow entity
        ],
        "src/domain/value_objects": [
            "__init__.py"
        ],
        "src/domain/services": [
            "__init__.py"
        ],

        # Application Layer - Use cases and orchestration
        "src/application": [
            "__init__.py"
        ],
        "src/application/handlers": [
            "__init__.py",
            "command_handler.py"  # Our command processing handler
        ],
        "src/application/use_cases": [
            "__init__.py"
        ],
        "src/application/services": [
            "__init__.py"
        ],

        # Infrastructure Layer - External concerns
        "src/infrastructure": [
            "__init__.py"
        ],
        "src/infrastructure/hardware": [
            "__init__.py",
            "factory.py"  # Our hardware factory
        ],
        "src/infrastructure/abstract": [
            "__init__.py",
            "camera_interface.py",
            "gpu_interface.py",
            "timing_interface.py",
            "display_interface.py"
        ],
        "src/infrastructure/macos": [
            "__init__.py",
            "mock_camera.py",
            "mock_processing.py",
            "macos_timing.py",
            "mock_display.py",
            "metal_gpu.py"
        ],
        "src/infrastructure/communication": [
            "__init__.py",
            "ipc_server.py"  # Our IPC communication server
        ],

        # Test Structure
        "tests": [
            "__init__.py",
            "conftest.py",
            "run_tests.py"
        ],
        "tests/unit": [
            "__init__.py"
        ],
        "tests/unit/domain": [
            "__init__.py",
            "test_workflow_state.py"
        ],
        "tests/unit/application": [
            "__init__.py",
            "test_command_handler.py"
        ],
        "tests/unit/infrastructure": [
            "__init__.py",
            "test_hardware_factory.py",
            "test_ipc_server.py"
        ],
        "tests/integration": [
            "__init__.py",
            "test_workflow_integration.py"
        ]
    }


def get_current_structure() -> Dict[str, List[str]]:
    """Get the current directory structure"""
    structure = {}

    # Start from src directory
    src_path = Path("src")
    if src_path.exists():
        for root, dirs, files in os.walk(src_path):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            rel_path = os.path.relpath(root, ".")
            python_files = [f for f in files if f.endswith('.py')]
            if python_files:
                structure[rel_path] = sorted(python_files)

    # Add tests directory
    tests_path = Path("tests")
    if tests_path.exists():
        for root, dirs, files in os.walk(tests_path):
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            rel_path = os.path.relpath(root, ".")
            python_files = [f for f in files if f.endswith('.py')]
            if python_files:
                structure[rel_path] = sorted(python_files)

    return structure


def verify_clean_architecture():
    """Verify Clean Architecture compliance"""
    print("🏗️  Verifying Clean Architecture Structure...")

    expected = get_expected_architecture()
    current = get_current_structure()

    issues = []
    successes = []

    # Check expected directories exist with correct files
    for directory, expected_files in expected.items():
        if directory in current:
            current_files = set(current[directory])
            expected_files_set = set(expected_files)

            # Check for missing files
            missing = expected_files_set - current_files
            if missing:
                issues.append(f"❌ {directory}: Missing files {missing}")

            # Check for our core files
            core_files = {
                "workflow_state.py", "command_handler.py",
                "factory.py", "ipc_server.py"
            }
            found_core = current_files & core_files
            if found_core:
                successes.append(f"✅ {directory}: Found core files {found_core}")
            elif expected_files_set & core_files:
                # Only flag if we expected core files here
                issues.append(f"❌ {directory}: Missing expected core files")
        else:
            issues.append(f"❌ Directory missing: {directory}")

    # Check for unexpected/duplicate directories
    unexpected_dirs = []
    for directory in current:
        # Look for problematic patterns
        if "backend/src" in directory:
            unexpected_dirs.append(directory)
        elif directory.count("/") > 3:  # Too deeply nested
            unexpected_dirs.append(directory)

    if unexpected_dirs:
        issues.append(f"❌ Unexpected/duplicate directories: {unexpected_dirs}")

    return issues, successes


def verify_file_contents():
    """Verify key files contain expected content"""
    print("\n📄 Verifying File Contents...")

    file_checks = {
        "src/domain/entities/workflow_state.py": [
            "class WorkflowState(Enum)",
            "class WorkflowStateMachine",
            "12-state",
            "Pydantic"
        ],
        "src/infrastructure/hardware/factory.py": [
            "class HardwareFactory",
            "PlatformType",
            "cross-platform",
            "ADR-0008"
        ],
        "src/infrastructure/communication/ipc_server.py": [
            "class IPCServer",
            "thin client",
            "ADR-0003"
        ],
        "src/application/handlers/command_handler.py": [
            "class CommandHandler",
            "CommandType",
            "Pydantic V2"
        ]
    }

    issues = []
    successes = []

    for file_path, required_content in file_checks.items():
        path = Path(file_path)
        if path.exists():
            with open(path, 'r') as f:
                content = f.read()

                missing_content = []
                for requirement in required_content:
                    if requirement.lower() not in content.lower():
                        missing_content.append(requirement)

                if missing_content:
                    issues.append(f"❌ {file_path}: Missing content {missing_content}")
                else:
                    successes.append(f"✅ {file_path}: Contains all required content")
        else:
            issues.append(f"❌ Missing critical file: {file_path}")

    return issues, successes


def verify_import_structure():
    """Verify imports follow clean architecture rules"""
    print("\n🔗 Verifying Import Dependencies...")

    # Domain layer should not import from Application or Infrastructure
    domain_files = list(Path("src/domain").rglob("*.py"))
    issues = []
    successes = []

    for file_path in domain_files:
        if file_path.name == "__init__.py":
            continue

        with open(file_path, 'r') as f:
            content = f.read()

            # Check for forbidden imports
            forbidden_imports = []
            if "from ..application" in content or "from src.application" in content:
                forbidden_imports.append("application")
            if "from ..infrastructure" in content or "from src.infrastructure" in content:
                forbidden_imports.append("infrastructure")

            if forbidden_imports:
                issues.append(f"❌ {file_path}: Domain layer importing from {forbidden_imports}")
            else:
                successes.append(f"✅ {file_path}: Clean domain layer dependencies")

    # Application layer should not import from Infrastructure (except interfaces)
    app_files = list(Path("src/application").rglob("*.py"))

    for file_path in app_files:
        if file_path.name == "__init__.py":
            continue

        with open(file_path, 'r') as f:
            content = f.read()

            # Infrastructure imports are OK if they're interfaces or communication
            if "from ...infrastructure" in content or "from src.infrastructure" in content:
                if "abstract" in content or "communication" in content:
                    successes.append(f"✅ {file_path}: Valid infrastructure interface import")
                else:
                    issues.append(f"⚠️  {file_path}: Direct infrastructure import (check if needed)")

    return issues, successes


def main():
    """Main verification function"""
    print("🔍 ARCHITECTURE VERIFICATION")
    print("=" * 60)

    all_issues = []
    all_successes = []

    # Run all verifications
    verifications = [
        verify_clean_architecture,
        verify_file_contents,
        verify_import_structure
    ]

    for verify_func in verifications:
        issues, successes = verify_func()
        all_issues.extend(issues)
        all_successes.extend(successes)

    # Print results
    print("\n" + "=" * 60)
    print("📊 ARCHITECTURE VERIFICATION RESULTS")
    print("=" * 60)

    print(f"\n✅ SUCCESSES ({len(all_successes)}):")
    for success in all_successes:
        print(f"   {success}")

    if all_issues:
        print(f"\n❌ ISSUES FOUND ({len(all_issues)}):")
        for issue in all_issues:
            print(f"   {issue}")

        print("\n🔧 RECOMMENDED ACTIONS:")
        print("   1. Remove duplicate/nested directory structures")
        print("   2. Ensure all core files are in correct locations")
        print("   3. Verify clean architecture dependency rules")

        return False
    else:
        print(f"\n🎉 PERFECT! ARCHITECTURE FULLY COMPLIANT")
        print("\n📋 Architecture Compliance Verified:")
        print("   ✅ Clean Architecture (Domain → Application → Infrastructure)")
        print("   ✅ Proper separation of concerns")
        print("   ✅ All core files in correct locations")
        print("   ✅ Dependencies follow architectural rules")
        print("   ✅ Test structure mirrors source structure")

        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)