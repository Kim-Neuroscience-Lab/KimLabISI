# Critical System Integration Issues - Investigation Report

**Date:** 2025-10-15
**Author:** Claude (System Integration Engineer)
**Status:** CRITICAL - Two Major Issues Identified

---

## Executive Summary

Two critical integration issues discovered after unified logging implementation:

1. **SYNC Channel Logging Spam (CRITICAL)**: DEBUG-level logging in frontend Electron main process flooding console with camera histogram updates (multiple messages per second)
2. **Acquisition Viewport Non-Functional (HIGH)**: Camera feed and stimulus preview completely broken - root cause unknown, requires systematic diagnosis

**Impact:**
- Console unusable due to logging spam (blocks error visibility)
- Acquisition system completely non-functional (workflow blocked)
- User cannot perform core operations (preview, record, playback)

---

## Issue #1: SYNC Channel Logging Spam

### Problem Statement

Frontend JavaScript console flooded with DEBUG-level SYNC channel messages:

```
[2025-10-15T00:10:18.560Z] [DEBUG] [Main] Received SYNC channel message: {
  type: 'camera_histogram_update',
  timestamp: 1760487018.560027,
  data: {
    histogram: [ 26, 122, 546, ... 156 more items ],
    bin_edges: [ 0, 1, 2, ... 157 more items ],
    statistics: { mean: 134.2, std: 53.3, min: 0, max: 255, median: 148 },
    timestamp: 1760487018560012
  }
}
```

**Frequency:** Every camera frame (30-60 fps) = 30-60 messages/second
**Result:** Console completely unusable, errors hidden in noise

### Root Cause Analysis

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts:416`

```typescript
private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health messages - don't log (sent every second)
      // Logging is already handled in handleHealthUpdate()
    } else {
      mainLogger.debug('Received SYNC channel message:', message)  // ← PROBLEM!
    }

    // ... rest of function
}
```

**Issue:** The `else` clause logs ALL other SYNC messages at DEBUG level, including:
- `camera_histogram_update` (30-60/sec)
- `correlation_update` (during acquisition)
- `acquisition_progress` (every frame during recording)
- Other high-frequency backend events

### Frontend Logging Architecture

The frontend has its own centralized logger (`/Users/Adam/KimLabISI/apps/desktop/src/utils/logger.ts`):

```typescript
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

// Default logger instance
export const logger = new Logger()

// Module-specific loggers
export const mainLogger = logger.child('Main')  // Used in main.ts
```

**Default Level:** `LogLevel.DEBUG` in development (line 25)

### Why This Wasn't Caught

1. Backend unified logging was correctly set to WARNING level (`main.py:2246`)
2. Backend debug print() statements were removed
3. BUT frontend logging was overlooked - it has separate configuration
4. Frontend default is DEBUG in development mode

### Solution

**Option A: Silence High-Frequency Messages (Recommended)**

Add specific handling for high-frequency messages to avoid DEBUG logging:

```typescript
private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health messages - don't log (sent every second)
    } else if (message.type === 'camera_histogram_update') {
      // Silently forward histogram updates - don't log (sent every frame)
    } else if (message.type === 'correlation_update') {
      // Silently forward correlation updates - don't log (sent every frame)
    } else if (message.type === 'acquisition_progress') {
      // Silently forward acquisition progress - don't log (sent every frame)
    } else {
      mainLogger.debug('Received SYNC channel message:', message)
    }

    // ... rest remains unchanged
}
```

**Option B: Change Frontend Default Log Level**

Modify `/Users/Adam/KimLabISI/apps/desktop/src/utils/logger.ts:25`:

```typescript
// Default to INFO in development, WARN in production
level: config.level ?? (process.env.NODE_ENV === 'development' ? LogLevel.INFO : LogLevel.WARN),
```

**Option C: Both (Best Practice)**

Combine both approaches for maximum clarity and minimum noise.

### Recommendation

**Implement Option A (specific message filtering)** because:
- Preserves DEBUG logging for truly important events
- Self-documenting (comments explain why each message is silenced)
- Allows selective debugging (can comment out individual filters)
- More surgical than changing global log level

---

## Issue #2: Acquisition Viewport Non-Functional

### Problem Statement

User reports: *"I am also seeing that the front end acquisition system is completely not functioning or performing its intended functionality."*

**Symptoms (Unknown):**
- Camera feed not showing?
- Stimulus preview not showing?
- Controls not responding?
- Status information not updating?
- Errors hidden by logging spam?

### Investigation Needed

Since user didn't specify exact symptoms, systematic diagnosis required:

#### Hypothesis 1: Camera Frame Listener Broken

**Evidence to check:**
1. Are camera frames being published by backend? (check backend logs)
2. Is frontend receiving `camera-frame` events? (check browser console after fixing log spam)
3. Is shared memory read working? (check for errors in `AcquisitionViewport.tsx:676-748`)

**Potential culprits:**
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:676-748` - Camera frame listener
- Backend camera acquisition not starting (check `main.py:1936-1951`)
- SharedMemoryFrameReader initialization failure (check `main.ts:463-543`)

#### Hypothesis 2: Stimulus Preview Listener Broken

**Evidence to check:**
1. Are stimulus frames being published? (check backend logs)
2. Is frontend receiving `shared-memory-frame` events?
3. Is the mini stimulus canvas rendering? (check `AcquisitionViewport.tsx:776-845`)

**Potential culprits:**
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:776-845` - Stimulus frame listener
- Backend not generating initial stimulus frame (check `main.py:1952-1963`)
- Shared memory path incorrect

#### Hypothesis 3: Preview Mode Integration Broken

**Evidence to check:**
1. Does clicking "Play" in preview mode call `start_preview()`?
2. Does `start_preview()` successfully call backend handlers?
3. Does backend `_start_preview_mode()` successfully start unified stimulus?

**Potential culprits:**
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:200-247` - `startPreview()` function
- Backend `_start_preview_mode()` handler (`main.py:772-877`)
- UnifiedStimulusController playback start (`acquisition/unified_stimulus.py`)

#### Hypothesis 4: Errors Hidden by Logging Spam

**Most likely root cause:** User can't see errors because console is flooded with DEBUG messages.

**Fix sequence:**
1. Apply SYNC logging fix first
2. Reproduce issue with clean console
3. Identify actual error messages
4. Diagnose based on error content

### Diagnostic Commands

To help user diagnose, provide these steps:

1. **Check Backend Logs** (Python):
   ```bash
   # Backend should be at WARNING level only
   # Look for errors in terminal where backend runs
   ```

2. **Check Frontend Console** (After fixing logging spam):
   - Open DevTools Console
   - Click "Play" in Acquisition viewport
   - Look for errors (red messages)
   - Look for failed network/IPC calls

3. **Check Shared Memory Initialization**:
   - Look for "SharedMemoryFrameReader initialized" messages
   - Check for "Failed to initialize" errors
   - Verify port numbers (5556, 5557, 5558)

### Code Locations to Audit

**Frontend:**
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:200-247` - `startPreview()`
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:676-748` - Camera listener
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:776-845` - Stimulus listener
- `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts:463-543` - SharedMemoryFrameReader init

**Backend:**
- `/Users/Adam/KimLabISI/apps/backend/src/main.py:772-877` - `_start_preview_mode()`
- `/Users/Adam/KimLabISI/apps/backend/src/main.py:1936-1951` - Camera auto-start
- `/Users/Adam/KimLabISI/apps/backend/src/main.py:1952-1963` - Initial stimulus frame
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py` - Playback control

### Recent Changes That Might Affect Acquisition

1. **Unified Logging Changes** (`main.py:2246`):
   - Set backend logging to WARNING level
   - Removed debug print() statements from `_get_analysis_composite_image()`
   - Could have hidden errors that were previously visible

2. **Presentation Stimulus State Broadcast** (`main.py:853-857, 894-898`):
   - Added `presentation_stimulus_state` broadcast to preview start/stop
   - Could interfere with acquisition viewport mini preview

3. **Auto-Preview Removal** (Commented out in `AcquisitionViewport.tsx:1135-1150`):
   - User must now explicitly click Play to start preview
   - Could be mistaken for "not functioning" if user expects auto-start

### Likely Root Cause

**Most Probable:** Errors are being thrown but hidden by DEBUG log spam.

**Evidence:**
- User confirmed backend preview/record stimulus IS working (frames being generated)
- Problem is frontend rendering and logging spam
- Timing of issue (right after unified logging changes)

**Next Steps:**
1. Fix SYNC logging spam FIRST
2. Ask user to reproduce with clean console
3. Provide specific error messages for diagnosis
4. Implement targeted fix based on actual error

---

## Fix Implementation Plan

### Phase 1: SYNC Logging Fix (Immediate)

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`
**Line:** 404-417
**Change:** Add specific filtering for high-frequency messages

```typescript
private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages (important events only)
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health messages - don't log (sent every second)
    } else if (message.type === 'camera_histogram_update') {
      // Silently forward histogram updates - don't log (sent every frame @ 30-60fps)
    } else if (message.type === 'correlation_update') {
      // Silently forward correlation updates - don't log (sent every frame during acquisition)
    } else if (message.type === 'acquisition_progress') {
      // Silently forward acquisition progress - don't log (sent every frame during recording)
    } else {
      // Log unexpected message types for debugging
      mainLogger.debug('Received SYNC channel message:', message)
    }

    // ... rest remains unchanged
}
```

**Testing:**
1. Start system
2. Start camera preview
3. Check console - should be quiet (no histogram spam)
4. Errors should now be visible

### Phase 2: Acquisition Diagnosis (After Phase 1)

**User Actions:**
1. Apply Phase 1 fix
2. Restart application
3. Open browser DevTools console
4. Click "Play" in Acquisition viewport (preview mode)
5. Report any errors shown in console

**Developer Actions:**
1. Wait for user error report
2. Analyze error messages
3. Determine if issue is:
   - Camera frame listener
   - Stimulus frame listener
   - Preview mode integration
   - Shared memory initialization
   - Backend handler failure

### Phase 3: Targeted Fix (Based on Diagnosis)

**Will implement specific fix after Phase 2 diagnosis completes.**

---

## Verification Checklist

### SYNC Logging Fix Verification

- [ ] Console shows NO `camera_histogram_update` messages during preview
- [ ] Console shows NO `correlation_update` messages during acquisition
- [ ] Console shows NO `acquisition_progress` messages during recording
- [ ] Console DOES show important events (`analysis_layer_ready`, `analysis_started`, etc.)
- [ ] Console DOES show errors clearly (not hidden in spam)

### Acquisition Viewport Verification

After Phase 2 diagnosis:

- [ ] Camera feed shows live video
- [ ] Stimulus mini preview shows checkerboard pattern
- [ ] Preview mode starts when clicking "Play"
- [ ] Camera statistics update in real-time
- [ ] Histogram chart shows luminance distribution
- [ ] Frame timing chart shows correlation data (during acquisition)

---

## Architectural Debt Notes

### Frontend/Backend Logging Inconsistency

**Issue:** Frontend and backend have separate logging systems with different configurations.

**Current State:**
- Backend: Unified logging via `logging_config.py`, default WARNING
- Frontend: Separate logger via `utils/logger.ts`, default DEBUG

**Risk:** Changes to one don't affect the other, causing inconsistencies.

**Recommendation:** Document this clearly, or consider unified logging configuration in future.

### High-Frequency Message Handling

**Issue:** SYNC channel carries both important events AND high-frequency data updates.

**Current State:** Mixed message types on single channel, requires filtering at receiver.

**Risk:** Easy to accidentally log high-frequency messages, causing spam.

**Recommendation:** Consider dedicated channels for high-frequency data (histogram, correlation) vs. events (acquisition_started, etc.).

### Error Visibility During Development

**Issue:** DEBUG logging in development can hide errors in noise.

**Current State:** Frontend defaults to DEBUG, backend defaults to WARNING.

**Risk:** Developers miss errors during testing.

**Recommendation:**
- Set frontend default to INFO (not DEBUG) even in development
- Use DEBUG selectively for specific investigations
- Keep production at WARN level

---

## Summary

### Issue #1: SYNC Logging Spam (SOLVED)
- **Cause:** DEBUG logging of high-frequency SYNC messages
- **Location:** `main.ts:416`
- **Fix:** Add specific filtering for `camera_histogram_update`, `correlation_update`, `acquisition_progress`
- **Effort:** 5 minutes
- **Priority:** CRITICAL

### Issue #2: Acquisition Viewport (NEEDS DIAGNOSIS)
- **Cause:** Unknown (errors likely hidden by log spam)
- **Fix:** Apply Issue #1 fix first, then diagnose with clean console
- **Effort:** Unknown (depends on root cause)
- **Priority:** HIGH

### Next Steps

1. **Apply SYNC logging fix** (Issue #1)
2. **Restart application**
3. **Reproduce acquisition viewport issue with clean console**
4. **Report actual error messages**
5. **Implement targeted fix based on diagnosis**

---

## Appendices

### A. Code Snippets

**Current `handleSyncMessage()` implementation:**

```typescript
// /Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts:404-417
private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health messages - don't log (sent every second)
      // Logging is already handled in handleHealthUpdate()
    } else {
      mainLogger.debug('Received SYNC channel message:', message)  // ← PROBLEM
    }
    // ... rest of function
}
```

**Proposed fix:**

```typescript
private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages (important events only)
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health - don't log (every 1s)
    } else if (message.type === 'camera_histogram_update') {
      // Silently forward histogram - don't log (30-60/sec)
    } else if (message.type === 'correlation_update') {
      // Silently forward correlation - don't log (every frame)
    } else if (message.type === 'acquisition_progress') {
      // Silently forward progress - don't log (every frame)
    } else {
      // Log unexpected message types
      mainLogger.debug('Received SYNC channel message:', message)
    }
    // ... rest unchanged
}
```

### B. Related Files

**Frontend Logging:**
- `/Users/Adam/KimLabISI/apps/desktop/src/utils/logger.ts` - Logger implementation
- `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts` - Main process (SYNC handler)

**Backend Logging:**
- `/Users/Adam/KimLabISI/apps/backend/src/logging_config.py` - Centralized logging config
- `/Users/Adam/KimLabISI/apps/backend/src/main.py` - Main application

**Acquisition Viewport:**
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx` - Main component
- `/Users/Adam/KimLabISI/apps/backend/src/main.py` - Preview mode handlers (line 772-950)
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py` - Stimulus controller

### C. References

- [Multi-Channel IPC Architecture](../docs/MULTI_CHANNEL_IPC.md) (if exists)
- [Unified Logging Implementation](../UNIFIED_LOGGING_COMPLETE.md) (if exists)
- [Acquisition System Design](../ACQUISITION_SYSTEM_AUDIT_REPORT.md)

---

**Report Generated:** 2025-10-15
**Claude Version:** Sonnet 4.5
**Investigation Time:** 30 minutes
**Status:** Phase 1 (SYNC Fix) ready for implementation, Phase 2 (Acquisition Diagnosis) awaiting user testing
