#!/usr/bin/env python3
"""Phase 8: Master Test Runner - Comprehensive Test Suite.

This script runs ALL tests for the refactored ISI Macroscope backend:
- Phase 1-7 unit tests
- Integration tests
- Code quality checks

Generates a comprehensive summary report and returns exit code 0
only if ALL tests pass.

Run with: python src/test_all.py
"""

import sys
import subprocess
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MasterTestRunner:
    """Orchestrates all test suites."""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.results: Dict[str, bool] = {}
        self.timings: Dict[str, float] = {}
        self.total_tests = 0
        self.total_passed = 0
        self.total_failed = 0

    def run_test_file(self, test_file: Path, description: str) -> Tuple[bool, float]:
        """Run a single test file and return success status and duration.

        Args:
            test_file: Path to test file
            description: Description for logging

        Returns:
            Tuple of (success, duration_seconds)
        """
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Running: {description}")
        logger.info(f"File: {test_file.name}")
        logger.info(f"{'=' * 80}")

        start_time = time.time()

        try:
            # Run test file
            result = subprocess.run(
                [sys.executable, str(test_file)],
                cwd=self.src_dir.parent,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per test
            )

            duration = time.time() - start_time

            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            # Check result
            success = (result.returncode == 0)

            if success:
                logger.info(f"\nRESULT: PASSED (in {duration:.2f}s)")
            else:
                logger.error(f"\nRESULT: FAILED (exit code {result.returncode}, after {duration:.2f}s)")

            return success, duration

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error(f"\nRESULT: TIMEOUT after {duration:.2f}s")
            return False, duration

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"\nRESULT: ERROR - {e}")
            return False, duration

    def run_phase_tests(self) -> bool:
        """Run all phase tests (1-7).

        Returns:
            True if all phase tests pass
        """
        logger.info("\n" + "=" * 80)
        logger.info("RUNNING PHASE TESTS (1-7)")
        logger.info("=" * 80)

        phase_tests = [
            ("test_phase1.py", "Phase 1: Infrastructure (IPC & Config)"),
            ("test_phase2.py", "Phase 2: Camera System"),
            ("test_phase3.py", "Phase 3: Stimulus System"),
            ("test_phase4.py", "Phase 4: Acquisition System"),
            ("test_phase5.py", "Phase 5: Analysis System"),
            ("test_phase6.py", "Phase 6: Main Application"),
            ("test_phase7.py", "Phase 7: Supporting Services"),
        ]

        all_passed = True

        for test_file_name, description in phase_tests:
            test_file = self.src_dir / test_file_name

            if not test_file.exists():
                logger.warning(f"Test file not found: {test_file_name} - SKIPPING")
                continue

            success, duration = self.run_test_file(test_file, description)
            self.results[description] = success
            self.timings[description] = duration

            if not success:
                all_passed = False

        return all_passed

    def run_integration_tests(self) -> bool:
        """Run integration tests.

        Returns:
            True if integration tests pass
        """
        logger.info("\n" + "=" * 80)
        logger.info("RUNNING INTEGRATION TESTS")
        logger.info("=" * 80)

        test_file = self.src_dir / "test_integration.py"

        if not test_file.exists():
            logger.error("Integration test file not found!")
            return False

        success, duration = self.run_test_file(test_file, "Phase 8: Integration Tests")
        self.results["Integration Tests"] = success
        self.timings["Integration Tests"] = duration

        return success

    def run_quality_tests(self) -> bool:
        """Run code quality tests.

        Returns:
            True if quality tests pass
        """
        logger.info("\n" + "=" * 80)
        logger.info("RUNNING CODE QUALITY TESTS")
        logger.info("=" * 80)

        test_file = self.src_dir / "test_quality.py"

        if not test_file.exists():
            logger.error("Quality test file not found!")
            return False

        success, duration = self.run_test_file(test_file, "Phase 8: Code Quality")
        self.results["Code Quality"] = success
        self.timings["Code Quality"] = duration

        return success

    def generate_summary_report(self) -> str:
        """Generate comprehensive summary report.

        Returns:
            Formatted summary report as string
        """
        report_lines = [
            "",
            "=" * 80,
            "COMPREHENSIVE TEST SUMMARY REPORT",
            "=" * 80,
            "",
            "Test Results:",
            "-" * 80,
        ]

        # Individual test results
        for test_name, passed in self.results.items():
            status = "PASS" if passed else "FAIL"
            duration = self.timings.get(test_name, 0.0)
            report_lines.append(f"  [{status}] {test_name:50s} ({duration:6.2f}s)")

        report_lines.append("-" * 80)

        # Count results
        passed_count = sum(1 for p in self.results.values() if p)
        failed_count = len(self.results) - passed_count
        total_duration = sum(self.timings.values())

        report_lines.extend([
            "",
            f"Total Test Suites: {len(self.results)}",
            f"Passed: {passed_count}",
            f"Failed: {failed_count}",
            f"Total Duration: {total_duration:.2f}s",
            "",
        ])

        # Overall result
        all_passed = all(self.results.values())

        if all_passed:
            report_lines.extend([
                "=" * 80,
                "OVERALL RESULT: ALL TESTS PASSED",
                "=" * 80,
                "",
                "The refactored ISI Macroscope backend is ready for deployment!",
                "",
            ])
        else:
            report_lines.extend([
                "=" * 80,
                "OVERALL RESULT: SOME TESTS FAILED",
                "=" * 80,
                "",
                "Please review the failed tests above and fix issues before deployment.",
                "",
                "Failed test suites:",
            ])
            for test_name, passed in self.results.items():
                if not passed:
                    report_lines.append(f"  - {test_name}")
            report_lines.append("")

        return "\n".join(report_lines)

    def run_all_tests(self) -> bool:
        """Run all test suites and generate report.

        Returns:
            True if all tests pass
        """
        logger.info("=" * 80)
        logger.info("ISI MACROSCOPE BACKEND - MASTER TEST RUNNER")
        logger.info("=" * 80)
        logger.info("")
        logger.info("This will run ALL tests for the refactored backend:")
        logger.info("  - Phase 1-7 unit tests")
        logger.info("  - Integration tests")
        logger.info("  - Code quality checks")
        logger.info("")

        start_time = time.time()

        # Run all test suites
        phase_passed = self.run_phase_tests()
        integration_passed = self.run_integration_tests()
        quality_passed = self.run_quality_tests()

        total_duration = time.time() - start_time

        # Generate and print report
        report = self.generate_summary_report()
        print(report)

        logger.info(f"Total execution time: {total_duration:.2f}s")

        # Return overall success
        all_passed = phase_passed and integration_passed and quality_passed
        return all_passed


def count_code_statistics(src_dir: Path) -> Dict[str, int]:
    """Count code statistics for the new codebase.

    Args:
        src_dir: Source directory to analyze

    Returns:
        Dictionary with code statistics
    """
    stats = {
        "total_files": 0,
        "total_lines": 0,
        "code_lines": 0,
        "comment_lines": 0,
        "blank_lines": 0,
        "total_modules": 0,
        "total_classes": 0,
        "total_functions": 0,
    }

    import ast

    for py_file in src_dir.rglob("*.py"):
        # Skip old code and cache
        if "isi_control" in str(py_file) or "__pycache__" in str(py_file):
            continue

        stats["total_files"] += 1

        try:
            with open(py_file) as f:
                content = f.read()
                lines = content.split('\n')

            stats["total_lines"] += len(lines)

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    stats["blank_lines"] += 1
                elif stripped.startswith('#'):
                    stats["comment_lines"] += 1
                else:
                    stats["code_lines"] += 1

            # Count modules, classes, functions
            try:
                tree = ast.parse(content)
                stats["total_modules"] += 1

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        stats["total_classes"] += 1
                    elif isinstance(node, ast.FunctionDef):
                        stats["total_functions"] += 1
            except:
                pass

        except Exception as e:
            logger.warning(f"Could not process {py_file}: {e}")

    return stats


def print_code_statistics():
    """Print code statistics for the refactored codebase."""
    logger.info("\n" + "=" * 80)
    logger.info("CODE STATISTICS - REFACTORED BACKEND")
    logger.info("=" * 80)

    src_dir = Path(__file__).parent
    stats = count_code_statistics(src_dir)

    logger.info(f"\nFile Metrics:")
    logger.info(f"  Total Python files: {stats['total_files']}")
    logger.info(f"  Total modules: {stats['total_modules']}")
    logger.info(f"  Total classes: {stats['total_classes']}")
    logger.info(f"  Total functions: {stats['total_functions']}")

    logger.info(f"\nLine Metrics:")
    logger.info(f"  Total lines: {stats['total_lines']}")
    logger.info(f"  Code lines: {stats['code_lines']}")
    logger.info(f"  Comment lines: {stats['comment_lines']}")
    logger.info(f"  Blank lines: {stats['blank_lines']}")

    if stats['code_lines'] > 0:
        comment_ratio = stats['comment_lines'] / stats['code_lines'] * 100
        logger.info(f"  Comment ratio: {comment_ratio:.1f}%")

    logger.info("")


def main():
    """Main entry point for master test runner."""
    src_dir = Path(__file__).parent

    # Print code statistics first
    print_code_statistics()

    # Run all tests
    runner = MasterTestRunner(src_dir)
    success = runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
