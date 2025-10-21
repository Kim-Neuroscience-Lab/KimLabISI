# SYNC Channel Logging Spam - FIXED

**Date:** 2025-10-15
**Status:** ✅ COMPLETE
**Priority:** CRITICAL

---

## Problem Summary

Frontend console was being flooded with DEBUG-level SYNC channel messages at 30-60 messages per second (every camera frame), making it impossible to see errors or important information.

**Example spam:**
```
[DEBUG] [Main] Received SYNC channel message: { type: 'camera_histogram_update', ... }
[DEBUG] [Main] Received SYNC channel message: { type: 'camera_histogram_update', ... }
[DEBUG] [Main] Received SYNC channel message: { type: 'camera_histogram_update', ... }
```

## Root Cause

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`
**Function:** `handleSyncMessage()` at line 404

The SYNC message handler was logging ALL unrecognized message types at DEBUG level, including high-frequency data updates like:
- `camera_histogram_update` (30-60/sec during preview)
- `correlation_update` (every frame during acquisition)
- `acquisition_progress` (every frame during recording)

## Fix Applied

Added specific filtering for high-frequency messages to prevent logging spam:

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

    // ... rest of function unchanged
}
```

**Key changes:**
1. Added explicit filtering for `camera_histogram_update` (30-60fps spam)
2. Added explicit filtering for `correlation_update` (acquisition spam)
3. Added explicit filtering for `acquisition_progress` (recording spam)
4. Kept DEBUG logging for truly unexpected message types
5. Added clear comments explaining why each message is silenced

## Expected Results

After restarting the application:

✅ **Console should be quiet** - No histogram/correlation/progress spam
✅ **Errors should be visible** - Important messages not hidden in noise
✅ **Important events still logged** - Analysis layer messages, startup events, etc.
✅ **Charts still work** - Data is still forwarded to frontend, just not logged

## Testing Checklist

- [ ] Restart application (frontend rebuild required)
- [ ] Open browser DevTools console
- [ ] Start camera preview (click "Play" in Acquisition viewport)
- [ ] Verify console is quiet (no `camera_histogram_update` spam)
- [ ] Verify histogram chart updates correctly (data still flowing)
- [ ] Check for any errors now visible in clean console

## Next Steps: Acquisition Viewport Diagnosis

Now that the console logging spam is fixed, we can diagnose the "acquisition system not functioning" issue.

**User: Please perform these steps:**

1. **Restart the application** (frontend needs rebuild to pick up logging fix)
2. **Open browser DevTools console** (right-click → Inspect → Console tab)
3. **Try to use Acquisition viewport:**
   - Click "Play" button in preview mode
   - Observe what happens
   - Check console for any errors (red messages)
4. **Report back:**
   - What errors appear in console?
   - Does camera feed show up?
   - Does stimulus mini preview show up?
   - What specific functionality is broken?

**With the logging spam gone, we should now be able to see the actual error messages that were previously hidden.**

## Files Changed

- `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts` (line 404-424)

## Related Documentation

- Full investigation report: `/Users/Adam/KimLabISI/CRITICAL_INTEGRATION_ISSUES_REPORT.md`
- Frontend logger: `/Users/Adam/KimLabISI/apps/desktop/src/utils/logger.ts`
- Backend logger: `/Users/Adam/KimLabISI/apps/backend/src/logging_config.py`

---

**Status:** SYNC logging spam fixed ✅
**Next:** Diagnose acquisition viewport issue with clean console
**Awaiting:** User testing and error report
