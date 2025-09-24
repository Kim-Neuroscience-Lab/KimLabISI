#!/bin/bash
"""
Quick Vulture Dead Code Analysis

Simple script to run vulture on the backend source code
"""

cd "$(dirname "$0")/.."

echo "🔍 Running Vulture dead code analysis on backend/src..."
echo "📁 Current directory: $(pwd)"
echo "=" * 50

# Run vulture with reasonable defaults
python -m vulture src/ \
    --min-confidence 80 \
    --sort-by-size \
    --exclude "**/tests/**,**/__pycache__/**,**/migrations/**"

echo ""
echo "✅ Analysis complete!"
echo ""
echo "💡 Tips:"
echo "- High confidence items (90%+) are usually safe to remove"
echo "- Medium confidence items (60-89%) need review"
echo "- Some findings may be false positives (framework methods, etc.)"
echo ""
echo "🔧 For advanced analysis with custom whitelist and report generation:"
echo "   python scripts/dead_code_analysis.py --help"