#!/usr/bin/env python3
"""
Test Runner for ISI Macroscope Control System

Runs the complete test suite with proper configuration and reporting.
Supports different test categories and platforms.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=None):
    """Run a command and handle output"""
    if description:
        print(f"\n{'='*60}")
        print(f"{description}")
        print(f"{'='*60}")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print("STDOUT:")
        print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if result.returncode != 0:
        print(f"Command failed with return code {result.returncode}")
        return False

    return True


def run_tests(test_type="all", verbose=False, coverage=True, platform=None):
    """Run tests based on specified criteria"""

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add coverage if requested
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_html"
        ])

    # Select tests based on type
    if test_type == "unit":
        cmd.append("tests/unit/")
        description = "Running Unit Tests"
    elif test_type == "integration":
        cmd.append("tests/integration/")
        description = "Running Integration Tests"
    elif test_type == "domain":
        cmd.append("tests/unit/domain/")
        description = "Running Domain Layer Tests"
    elif test_type == "application":
        cmd.append("tests/unit/application/")
        description = "Running Application Layer Tests"
    elif test_type == "infrastructure":
        cmd.append("tests/unit/infrastructure/")
        description = "Running Infrastructure Layer Tests"
    elif test_type == "workflow":
        cmd.extend([
            "tests/unit/domain/test_workflow_state.py",
            "tests/integration/test_workflow_integration.py"
        ])
        description = "Running Workflow Tests"
    elif test_type == "hardware":
        cmd.append("tests/unit/infrastructure/test_hardware_factory.py")
        description = "Running Hardware Tests"
    elif test_type == "ipc":
        cmd.extend([
            "tests/unit/infrastructure/test_ipc_server.py",
            "tests/unit/application/test_command_handler.py"
        ])
        description = "Running IPC Communication Tests"
    else:  # all
        cmd.append("tests/")
        description = "Running All Tests"

    # Add platform-specific markers
    if platform:
        if platform == "macos":
            cmd.extend(["-m", "not hardware or mock"])
        elif platform == "windows":
            cmd.extend(["-m", "not mock"])
        elif platform == "cross_platform":
            cmd.extend(["-m", "cross_platform"])

    # Add other useful options
    cmd.extend([
        "--tb=short",  # Shorter traceback format
        "--strict-markers",  # Strict marker checking
        "-x",  # Stop on first failure (remove this for full runs)
    ])

    return run_command(cmd, description)


def run_linting():
    """Run code linting checks"""
    print("\n" + "="*60)
    print("Running Code Quality Checks")
    print("="*60)

    # Check if ruff is available
    try:
        result = subprocess.run(["ruff", "--version"], capture_output=True)
        if result.returncode == 0:
            print("Running ruff linting...")
            if not run_command(["ruff", "check", "src/", "tests/"], "Ruff Linting"):
                return False
        else:
            print("Ruff not available, skipping linting")
    except FileNotFoundError:
        print("Ruff not found, skipping linting")

    # Check if mypy is available
    try:
        result = subprocess.run(["mypy", "--version"], capture_output=True)
        if result.returncode == 0:
            print("Running mypy type checking...")
            if not run_command(["mypy", "src/"], "MyPy Type Checking"):
                return False
        else:
            print("MyPy not available, skipping type checking")
    except FileNotFoundError:
        print("MyPy not found, skipping type checking")

    return True


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="Run ISI Macroscope Control System Tests")

    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=[
            "all", "unit", "integration", "domain", "application",
            "infrastructure", "workflow", "hardware", "ipc"
        ],
        help="Type of tests to run"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Disable coverage reporting"
    )

    parser.add_argument(
        "--platform",
        choices=["macos", "windows", "cross_platform"],
        help="Run platform-specific tests"
    )

    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run linting and type checking"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test run (unit tests only, no coverage)"
    )

    args = parser.parse_args()

    # Handle quick mode
    if args.quick:
        args.test_type = "unit"
        args.no_coverage = True

    success = True

    # Run linting if requested
    if args.lint:
        success = run_linting() and success

    # Run tests
    success = run_tests(
        test_type=args.test_type,
        verbose=args.verbose,
        coverage=not args.no_coverage,
        platform=args.platform
    ) and success

    # Summary
    print("\n" + "="*60)
    if success:
        print("✅ All tests passed!")
        print("\nTest Categories Available:")
        print("  python tests/run_tests.py unit          # Unit tests only")
        print("  python tests/run_tests.py integration   # Integration tests only")
        print("  python tests/run_tests.py workflow      # Workflow-specific tests")
        print("  python tests/run_tests.py hardware      # Hardware-specific tests")
        print("  python tests/run_tests.py ipc           # IPC communication tests")
        print("  python tests/run_tests.py --quick       # Quick unit test run")
        print("  python tests/run_tests.py --lint        # Include linting/type checks")

        if not args.no_coverage:
            print(f"\n📊 Coverage report generated in: coverage_html/index.html")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()