# Quick Start Testing Guide
**What Changed:** Fixed stimulus integration after PNG compression removal

---

## What Was Fixed

1. ✓ **Stimulus Generation badge now persists** - Won't disappear when you navigate away
2. ✓ **Acquisition viewport shows if stimulus is ready** - Green badge = ready, Yellow badge = need to pre-generate
3. ✓ **All acquisition modes work correctly** - Preview, Record, and Playback

---

## Quick Test (5 minutes)

### Step 1: Check Badge Persistence
1. Open app → Go to "Stimulus Generation" tab
2. Click "Pre-Generate All Directions"
3. Wait for green "Complete ✓" badge
4. Switch to "Acquisition" tab
5. Switch back to "Stimulus Generation" tab
6. **Check:** Badge still shows "Complete ✓" (not blank)

**If it works:** ✓ Badge persistence is fixed!

---

### Step 2: Check Acquisition Status
1. Go to "Acquisition" tab
2. Look at "Camera Information" panel (middle section)
3. **Check:** You should see new section called "Stimulus Library"
4. **Check:** Shows one of:
   - "Checking status..." (gray) = loading
   - "Stimulus Ready ✓" (green) = ready to record
   - "Pre-generate Required ⚠" (yellow) = need to pre-generate first

**If you see the status:** ✓ Status indicator is working!

---

### Step 3: Test Preview Mode
1. In Acquisition viewport, select "preview" mode
2. Click Play button (▶)
3. Check "Show on Presentation Monitor" checkbox
4. **Check:** Stimulus animates on your second monitor
5. Click Pause button (⏸)

**If stimulus shows:** ✓ Preview mode works!

---

### Step 4: Test Record Mode
1. In Acquisition viewport, select "record" mode
2. **Check:** Stimulus status shows "Stimulus Ready ✓" (green)
3. Click Record button (red ⏺)
4. Confirm the filter warning dialog
5. **Check:** Recording starts, camera captures, stimulus plays
6. Wait 10 seconds
7. Click Stop button (⏹)

**If recording works:** ✓ Record mode works!

---

## What to Look For

### Good Signs ✓
- Badge shows "Complete ✓" in Stimulus Generation
- Status shows "Stimulus Ready ✓" (green) in Acquisition
- Preview mode plays smoothly
- Record mode starts immediately
- No error messages in logs

### Bad Signs ✗
- Badge disappears when switching tabs
- Status stuck on "Checking status..." forever
- Acquisition fails with error "library not loaded"
- Stimulus doesn't show on presentation monitor
- Console shows errors about "unified_stimulus_get_status"

---

## If Something Doesn't Work

### Issue: Badge Still Disappears
**Check:**
1. Open browser console (F12)
2. Look for errors about "unified_stimulus_get_status"
3. Check if backend is responding

**Fix:**
- Restart the app
- If still broken, report the error message

---

### Issue: Status Stuck on "Checking status..."
**Check:**
1. Is backend running? (Look for console output)
2. Is frontend connected? (Look for "Backend ready" message)

**Fix:**
- Wait 5 seconds (may still be loading)
- Restart the app
- Check backend logs for errors

---

### Issue: "Pre-generate Required" Won't Go Away
**Check:**
1. Did you actually pre-generate? (Go to Stimulus Generation tab)
2. Did pre-generation succeed? (Green badge should show)

**Fix:**
- Pre-generate in Stimulus Generation tab
- Wait for "Complete ✓" badge
- Go back to Acquisition tab
- Status should update to "Stimulus Ready ✓"

---

## Advanced Testing (Optional)

### Test Library Invalidation
1. Pre-generate stimulus (green badge)
2. Go to Control Panel
3. Change stimulus bar width from 20 to 25
4. Go back to Stimulus Generation
5. **Check:** Badge resets to "Pre-Generate" button (library invalidated)
6. Pre-generate again
7. **Check:** Works correctly

---

### Test Auto Pre-generation
1. Restart app (clear everything)
2. Don't pre-generate manually
3. Go to Acquisition viewport
4. Select "record" mode
5. Click Record button
6. **Check:** Backend auto pre-generates (may take 30-60 seconds)
7. **Check:** Recording starts automatically when ready

**This tests backend's async pre-generation feature**

---

## Console Commands (For Debugging)

If you see errors, these commands help diagnose:

```javascript
// In browser console (F12)

// Check if IPC is working
window.electronAPI

// Should show object with methods like:
// - sendCommand
// - onSyncMessage
// - onSharedMemoryFrame
```

---

## Log Files to Check

If something breaks:
1. Backend logs: Look for errors about "unified_stimulus"
2. Frontend console: Look for errors about "sendCommand failed"
3. Sync messages: Look for "unified_stimulus_pregeneration_complete"

---

## Expected Timing

- Status query: < 5ms (instant)
- Pre-generation: 30-60 seconds (one-time)
- Badge update: Instant
- Preview start: < 100ms
- Record start: < 100ms (if already pre-generated)
- Record start: 30-60 seconds (if auto pre-generating)

---

## Success Criteria

All these should work:
- ✓ Badge persists across tab switching
- ✓ Status shows correct state (ready vs not ready)
- ✓ Preview mode plays stimulus
- ✓ Record mode captures data
- ✓ No console errors
- ✓ Performance is smooth

---

## Quick Checklist

Before reporting success:
- [ ] Badge persists (test by switching tabs)
- [ ] Status indicator shows up in Acquisition viewport
- [ ] Status is correct (green when ready, yellow when not)
- [ ] Preview mode works
- [ ] Record mode works
- [ ] No errors in console

---

## If All Tests Pass

Great! The integration is working correctly. The fixes solved:
1. State persistence issue
2. Status visibility issue
3. Integration feedback issue

You can now use all acquisition modes normally.

---

## If Tests Fail

Please report:
1. Which test failed
2. What error message you saw (if any)
3. Browser console output
4. Backend log output

Include this information in your bug report for fastest resolution.

---

**Quick Start Guide Created:** 2025-10-14
**Estimated Testing Time:** 5-10 minutes for basic tests
**Full Testing Time:** 15-20 minutes with advanced tests
