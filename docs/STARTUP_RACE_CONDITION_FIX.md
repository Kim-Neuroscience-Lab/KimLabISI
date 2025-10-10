# Startup Race Condition Fix

## Problem
Application was getting stuck on the ready state during startup.

## Root Cause (Identified by Codebase Auditor)
**Duplicate handshake triggers** created a race condition where `frontend_ready` was sent BEFORE ZeroMQ subscriptions were established:

1. **main.ts line 505**: Triggered handshake on `zeromq_ready` message (TOO EARLY)
2. **SystemContext.tsx line 130**: Triggered handshake on `waiting_frontend` message (CORRECT)

**Result**: Frontend sent `frontend_ready` before subscribing to SYNC channel → Backend sent `parameters_snapshot` → Frontend missed it → Stuck waiting forever.

## Fixes Applied

### Fix 1: Remove Premature Handshake Trigger
**File**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`
**Lines**: 502-508

**Before**:
```typescript
if (message.type === 'zeromq_ready') {
  mainLogger.info('Backend ZeroMQ ready - connecting to channels...')
  await this.performFrontendHandshake()  // ❌ SENDS frontend_ready TOO EARLY
}
```

**After**:
```typescript
if (message.type === 'zeromq_ready') {
  mainLogger.info('Backend ZeroMQ ready - initializing subscriptions...')
  await this.initializeZeroMQConnections()  // ✅ ONLY initialize subscriptions
  mainLogger.info('ZeroMQ subscriptions established - waiting for backend waiting_frontend state...')
}
// Note: Frontend handshake will be triggered by waiting_frontend state (handled in SystemContext.tsx)
```

### Fix 2: Remove Duplicate system_state Handling
**File**: `/Users/Adam/KimLabISI/apps/desktop/src/context/SystemContext.tsx`
**Lines**: 216-217

**Removed**: Entire `system_state` handling block from CONTROL channel handler (lines 216-233 in old version)

**Reason**: `system_state` messages ONLY come via SYNC channel. Duplicate handling created race conditions.

## Correct Startup Flow (After Fixes)

```
1. Backend: zeromq_ready (CONTROL)
   → Electron: initializeZeroMQConnections() (ONLY subscribes, doesn't send anything)

2. Backend: waiting_frontend (SYNC)
   → SystemContext: performHandshake() sends frontend_ready (CORRECT timing)

3. Backend: _handle_frontend_ready() executes
   → Verifies hardware
   → Sends parameters_snapshot (SYNC) ✅ Frontend IS subscribed now
   → Sends system_state: ready (SYNC)

4. Frontend:
   → Receives parameters_snapshot → sets parametersReceived = true
   → Receives system_state: ready → sets readyStateReceived = true
   → Both flags true → setIsReady(true) → UI enables ✅
```

## Architecture Principles Restored

1. **Single Source of Truth (SSoT)**: Only ONE code path triggers handshake (SystemContext.tsx)
2. **Separation of Concerns (SoC)**: Electron main process only manages infrastructure, React context manages coordination
3. **Channel Separation**: SYNC messages only handled in SYNC handler, not duplicated in CONTROL
4. **Proper Async Sequencing**: Subscriptions established BEFORE messages are sent

## Testing
After these fixes, the application should:
1. Subscribe to ZeroMQ channels first
2. Send `frontend_ready` only after subscriptions are ready
3. Receive all messages from backend
4. Transition to ready state without getting stuck

## Files Modified
- `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts` (lines 502-508)
- `/Users/Adam/KimLabISI/apps/desktop/src/context/SystemContext.tsx` (lines 216-217)
