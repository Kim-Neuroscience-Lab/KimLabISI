#!/usr/bin/env python3
"""
Quick Vulture Analysis

Simple script to run dead code analysis with sensible defaults
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run quick vulture analysis"""
    backend_dir = Path(__file__).parent.parent
    src_dir = backend_dir / "src"

    if not src_dir.exists():
        print(f"❌ Source directory not found: {src_dir}")
        sys.exit(1)

    print("🔍 Quick Dead Code Analysis")
    print("=" * 40)
    print(f"📁 Analyzing: {src_dir}")
    print(f"🎯 High confidence findings only (95%+)")
    print()

    # Run vulture with high confidence threshold
    cmd = [
        "python", "-m", "vulture",
        str(src_dir),
        "--min-confidence", "95",
        "--sort-by-size"
    ]

    try:
        result = subprocess.run(cmd, cwd=backend_dir)

        print()
        print("✅ Quick analysis complete!")
        print()
        print("💡 Tips:")
        print("- Items shown are 95%+ confidence - usually safe to clean up")
        print("- For detailed report: python scripts/dead_code_analysis.py --help")
        print("- For lower confidence analysis, use --min-confidence option")

        return result.returncode == 0

    except KeyboardInterrupt:
        print("\n⏹️  Analysis interrupted")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)