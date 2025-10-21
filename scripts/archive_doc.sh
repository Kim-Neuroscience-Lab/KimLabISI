#!/bin/bash
# Archive documentation file with timestamp prefix
# Usage: ./scripts/archive_doc.sh <file_path>

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <file_path>"
    echo "Example: $0 ACQUISITION_SYSTEM_AUDIT_REPORT.md"
    exit 1
fi

FILE_PATH="$1"
ARCHIVE_DIR="docs/archive/2025-10-14"

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "Error: File not found: $FILE_PATH"
    exit 1
fi

# Get file modification time in format YYYYMMDD_HHMM
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    TIMESTAMP=$(stat -f "%Sm" -t "%Y%m%d_%H%M" "$FILE_PATH")
else
    # Linux
    TIMESTAMP=$(stat -c "%y" "$FILE_PATH" | awk '{print $1"_"$2}' | tr -d ':' | tr -d '-' | cut -c 1-13)
fi

# Get filename without path
FILENAME=$(basename "$FILE_PATH")

# Create timestamped filename
TIMESTAMPED_NAME="${TIMESTAMP}_${FILENAME}"

# Create archive directory if it doesn't exist
mkdir -p "$ARCHIVE_DIR"

# Move file
echo "Archiving: $FILE_PATH"
echo "      → $ARCHIVE_DIR/$TIMESTAMPED_NAME"
mv "$FILE_PATH" "$ARCHIVE_DIR/$TIMESTAMPED_NAME"

echo "✓ Archived successfully"
