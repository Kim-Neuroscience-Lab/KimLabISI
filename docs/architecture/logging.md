# Logging Architecture

**Last Updated**: 2025-10-15
**Status**: Active
**Related**: [Development Guide](../guides/development.md), [ADR-006: Unified Logging](../decisions/006-unified-logging.md)

---

## Overview

The ISI Macroscope uses a **unified logging architecture** across backend (Python) and frontend (TypeScript) to ensure clean, actionable console output showing only warnings and errors by default.

**Key Principle**: Console output is a production interface. Verbose debug/info logging clutters the console and obscures actual problems.

---

## Log Levels

### Standard Levels (Both Backend and Frontend)

| Level | Usage | Example |
|-------|-------|---------|
| **ERROR** | Unrecoverable errors, failed operations | `logger.error("Camera acquisition failed")` |
| **WARN** | Recoverable issues, degraded functionality | `logger.warning("No hardware timestamps - using software")` |
| **INFO** | Informational messages (disabled by default) | `logger.info("Camera acquisition started")` |
| **DEBUG** | Detailed diagnostic information (disabled by default) | `logger.debug("Frame metadata: {metadata}")` |

### Default Configuration

- **Production**: `WARN` level (only warnings and errors)
- **Development**: `WARN` level (same as production for consistency)
- **Testing**: `DEBUG` level (full diagnostics)

**Rationale**: Development and production should have identical logging behavior. Use dedicated debug flags for diagnostics, not blanket INFO logging.

---

## Backend Logging (Python)

### Configuration Location

**File**: `/apps/backend/src/logging_config.py`

```python
def configure_logging(level: int = logging.WARNING) -> None:
    """Configure centralized logging for entire backend.

    Args:
        level: Logging level (default: WARNING for clean console output)
    """
    # Configure root logger format
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # CRITICAL: Explicitly set root logger level to enforce across all child loggers
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
```

### Usage Pattern

```python
import logging

logger = logging.getLogger(__name__)  # Use module-level logger

# Good - respects configured log level
logger.error("Critical failure: {error}")
logger.warning("Hardware limitation detected")
logger.info("Operational milestone reached")  # Hidden by default
logger.debug("Detailed state: {state}")        # Hidden by default

# Bad - bypasses logging infrastructure
print("Some message")  # ❌ Never use print() in production code
```

### Main Entry Point

**File**: `/apps/backend/src/main.py`

```python
from logging_config import configure_logging

# Set log level to WARNING (only show warnings and errors)
configure_logging(level=logging.WARNING)
```

### Statistics (as of 2025-10-15)

- **Total logger.info() calls**: 437 across 20 files
- **Automatically silenced**: All 437 (no code changes needed)
- **Console output reduction**: ~100+ lines → <10 lines at startup

---

## Frontend Logging (TypeScript)

### Configuration Location

**File**: `/apps/desktop/src/utils/logger.ts`

```typescript
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3
}

export class Logger {
  private level: LogLevel

  constructor(config: LoggerConfig) {
    // Default to WARN level (only warnings and errors)
    this.level = config.level ?? LogLevel.WARN
  }

  debug(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.DEBUG) {
      console.debug(`[${this.name}] ${message}`, ...args)
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.INFO) {
      console.log(`[${this.name}] ${message}`, ...args)
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.WARN) {
      console.warn(`[${this.name}] ${message}`, ...args)
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.ERROR) {
      console.error(`[${this.name}] ${message}`, ...args)
    }
  }
}
```

### Usage Pattern

```typescript
import { componentLogger } from '../utils/logger'

// Good - respects configured log level
componentLogger.error("Failed to start acquisition", error)
componentLogger.warn("Camera not found")
componentLogger.info("Preview started")   // Hidden by default
componentLogger.debug("Frame metadata", metadata)  // Hidden by default

// Bad - bypasses logging infrastructure
console.log("Some message")  // ❌ Never use console.log() directly
```

### Enforcement

**ESLint Rule** (recommended): Ban direct `console.*` usage

```json
{
  "rules": {
    "no-console": ["error", {
      "allow": []  // No direct console usage allowed
    }]
  }
}
```

---

## Log Level Override (Temporary Debugging)

### Backend

```bash
# Set environment variable before starting
export ISI_LOG_LEVEL=DEBUG
./setup_and_run.sh
```

**Implementation** (main.py):
```python
import os

log_level_str = os.getenv('ISI_LOG_LEVEL', 'WARNING')
log_level = getattr(logging, log_level_str.upper(), logging.WARNING)
configure_logging(level=log_level)
```

### Frontend

**Implementation** (logger.ts):
```typescript
const debugMode = localStorage.getItem('ISI_DEBUG_MODE') === 'true'
const defaultLevel = debugMode ? LogLevel.DEBUG : LogLevel.WARN
```

**Usage** (Browser Console):
```javascript
// Enable debug mode
localStorage.setItem('ISI_DEBUG_MODE', 'true')
location.reload()

// Disable debug mode
localStorage.removeItem('ISI_DEBUG_MODE')
location.reload()
```

---

## Promoting Critical Messages to WARN

Not all operational messages should be hidden. Promote truly critical informational messages to WARNING level so they appear in console.

### Examples of Messages That Should Use WARN

```python
# System lifecycle events
logger.warning("System ready - frontend can transition")
logger.warning("Camera acquisition started for preview")
logger.warning("Hardware verification complete")

# Critical state changes
logger.warning("Development mode enabled - software timestamps in use")
logger.warning("No hardware timestamps available - degraded accuracy")

# User-facing milestones
logger.warning("Analysis complete - results saved to {path}")
logger.warning("Acquisition complete - {total_frames} frames recorded")
```

### Examples of Messages That Should Stay INFO

```python
# Internal operational details
logger.info("Parameter manager initialized")
logger.info("ZeroMQ channel created on port {port}")
logger.info("Loading session data for direction {direction}")

# Routine events
logger.info("Frame {frame_id} captured")
logger.info("Shared memory buffer allocated")
```

**Guideline**: If a developer or user needs to see it during normal operation, use WARN. If it's only useful for debugging, use INFO or DEBUG.

---

## Anti-Patterns

### ❌ Don't: Use print() statements

```python
print("Camera started")  # Bypasses logging infrastructure
```

### ❌ Don't: Use console.log() directly

```typescript
console.log("Received frame")  // Bypasses logging infrastructure
```

### ❌ Don't: Log in tight loops

```python
while True:
    logger.debug(f"Processing frame {i}")  # Even with DEBUG level, this is spam
```

### ❌ Don't: Include sensitive data in logs

```python
logger.info(f"User credentials: {username}:{password}")  # Security risk
```

### ✅ Do: Use structured logging with context

```python
logger.warning("Camera acquisition failed", extra={
    "camera_name": camera_name,
    "error_type": type(error).__name__,
    "timestamp": time.time()
})
```

---

## Testing Log Output

### Backend Test

```bash
cd apps/backend
.venv/bin/python -c "
import logging
from logging_config import configure_logging

configure_logging(level=logging.WARNING)
logger = logging.getLogger('test')

logger.debug('This should NOT appear')
logger.info('This should NOT appear')
logger.warning('This SHOULD appear ✓')
logger.error('This SHOULD appear ✓')
"
```

**Expected Output**:
```
2025-10-15 14:45:10 - test - WARNING - This SHOULD appear ✓
2025-10-15 14:45:10 - test - ERROR - This SHOULD appear ✓
```

### Frontend Test

Open browser console and run:

```javascript
// Should see only warnings and errors
componentLogger.debug("Hidden")  // Nothing
componentLogger.info("Hidden")   // Nothing
componentLogger.warn("Visible")  // ⚠️ [component] Visible
componentLogger.error("Visible") // ❌ [component] Visible
```

---

## Audit Results (2025-10-15)

### Backend Violations Identified

- **437** `logger.info()` calls across 20 files
- **0** `print()` statements (good!)

**Resolution**: All silenced by root logger level enforcement (no code changes needed)

### Frontend Violations Identified

- **7** direct `console.log()` statements
- **0** `console.debug()` statements

**Resolution**: All removed and replaced with proper logger calls

### Console Output Improvement

- **Before**: ~100+ lines of INFO-level spam at startup
- **After**: <10 lines showing only actual warnings/errors
- **Signal-to-noise ratio**: 5% → 100%

---

## Related Documentation

- [Development Guide](../guides/development.md) - Coding standards
- [ADR-006: Unified Logging](../decisions/006-unified-logging.md) - Architecture decision record
- [Troubleshooting Guide](../guides/troubleshooting.md) - Using logs for debugging

---

## Future Improvements

1. **Structured Logging**: Add JSON log output option for log aggregation tools
2. **Log Rotation**: Implement automatic log file rotation for long-running sessions
3. **Performance Metrics**: Add performance logging at WARN level for critical paths
4. **Error Reporting**: Integrate error logging with error tracking service (e.g., Sentry)

---

**Version**: 1.0
**Last Audit**: 2025-10-15
**Next Review**: 2026-01-15
