# Frontend Migration Guide: Connecting to Refactored Backend

## Overview

This guide walks through the safest way to migrate the Electron desktop app from the old `isi_control.main` backend to the new refactored `src.main` backend.

**Status:** New backend is 100% backward compatible - same IPC protocol, same commands, same config format.

## Migration Strategy: Dual-Boot with Environment Variable

We'll implement a **switchable backend** system that allows toggling between old and new backends via environment variable, with easy rollback.

---

## Step 1: Update Electron Main Process (Dual-Boot Support)

**File:** `apps/desktop/src/electron/main.ts`

**Current line 281:**
```typescript
const poetryArgs = [...poetryCommandArgs, 'run', 'python', '-u', '-m', 'isi_control.main']
```

**Replace with:**
```typescript
// Allow switching between old and new backend via environment variable
// USE_NEW_BACKEND=1 -> new refactored backend (src.main)
// USE_NEW_BACKEND=0 or unset -> old backend (isi_control.main) - DEFAULT
const backendModule = process.env.USE_NEW_BACKEND === '1' ? 'src.main' : 'isi_control.main'
mainLogger.info(`Using backend module: ${backendModule}`)

const poetryArgs = [...poetryCommandArgs, 'run', 'python', '-u', '-m', backendModule]
```

**Why this approach?**
- ✅ **Safe:** Old backend remains default
- ✅ **Testable:** Easy to switch for testing
- ✅ **Reversible:** One environment variable change to rollback
- ✅ **No code duplication:** Single codebase supports both

---

## Step 2: Testing Sequence (Recommended Order)

### 2.1 Test Old Backend (Baseline)

Ensure current system works:

```bash
cd /Users/Adam/KimLabISI/apps/desktop
npm run dev
```

**Verify:**
- ✅ Desktop app opens
- ✅ Backend connects
- ✅ Camera preview works
- ✅ Stimulus generation works
- ✅ Acquisition works
- ✅ Analysis works

**If any issues:** Fix before proceeding!

---

### 2.2 Test New Backend (Standalone)

Test new backend independently:

```bash
cd /Users/Adam/KimLabISI/apps/backend

# Verify imports
.venv/bin/python -c "from src.main import main; print('✓ OK')"

# Run comprehensive tests
.venv/bin/python src/test_all.py
```

**Expected:** All tests should pass (as they did before)

---

### 2.3 Test New Backend with Frontend

Switch to new backend:

```bash
cd /Users/Adam/KimLabISI/apps/desktop

# Set environment variable for new backend
export USE_NEW_BACKEND=1

# Start desktop app
npm run dev
```

**Verify same checklist:**
- ✅ Desktop app opens
- ✅ Backend connects (watch for "Using backend module: src.main" in logs)
- ✅ Camera preview works
- ✅ Stimulus generation works
- ✅ Acquisition works
- ✅ Analysis works

**If issues found:**
```bash
# Switch back to old backend immediately
unset USE_NEW_BACKEND
npm run dev
```

---

### 2.4 Side-by-Side Comparison Testing

Run both backends and compare:

**Terminal 1 (Old Backend):**
```bash
cd /Users/Adam/KimLabISI/apps/desktop
unset USE_NEW_BACKEND
npm run dev
# Test and document behavior
```

**Terminal 2 (New Backend):**
```bash
cd /Users/Adam/KimLabISI/apps/desktop
export USE_NEW_BACKEND=1
npm run dev
# Test and verify identical behavior
```

**Compare:**
- Health message format
- IPC command responses
- Camera frame metadata
- Stimulus rendering
- Performance characteristics
- Error handling

---

## Step 3: Integration Testing Checklist

### Core Functionality
- [ ] **Startup**: Backend starts and connects within 15 seconds
- [ ] **Health Monitoring**: Health messages appear in UI
- [ ] **ZeroMQ Handshake**: Frontend<->Backend handshake succeeds

### Camera System
- [ ] **Camera Detection**: `detect_cameras` command returns cameras
- [ ] **Camera Start**: `start_camera_acquisition` starts capture
- [ ] **Camera Frames**: Live camera frames appear in preview
- [ ] **Camera Stop**: `stop_camera_acquisition` stops cleanly
- [ ] **Camera Histogram**: Histogram data received

### Stimulus System
- [ ] **Stimulus Generation**: Stimulus frames render correctly
- [ ] **Shared Memory**: Stimulus shared memory works
- [ ] **Presentation Window**: Stimulus displays on secondary monitor
- [ ] **Direction Changes**: All 4 directions (LR, RL, TB, BT) work

### Acquisition System
- [ ] **Preview Mode**: Preview mode starts successfully
- [ ] **Record Mode**: Recording creates HDF5 files
- [ ] **Synchronization**: Camera-stimulus sync timestamps correct
- [ ] **State Transitions**: Mode transitions work smoothly
- [ ] **Session Metadata**: Session files have correct metadata

### Analysis System
- [ ] **Analysis Start**: `start_analysis` command works
- [ ] **FFT Processing**: Fourier analysis completes
- [ ] **Visualization**: Phase/amplitude maps render
- [ ] **Progress Updates**: Analysis progress updates received
- [ ] **Results Save**: Analysis results saved to HDF5

### Parameter System
- [ ] **Get Parameters**: `get_all_parameters` returns config
- [ ] **Update Parameters**: `update_parameter_group` updates config
- [ ] **Persistence**: Parameter changes persist

### Error Handling
- [ ] **Invalid Commands**: Invalid commands return error responses
- [ ] **Hardware Errors**: Hardware errors handled gracefully
- [ ] **Disconnection**: Backend disconnection detected
- [ ] **Reconnection**: Backend reconnection works

---

## Step 4: Make New Backend Default (When Ready)

After thorough testing (recommended: 1-2 weeks of testing new backend), make it default:

**Update `apps/desktop/src/electron/main.ts` line 281:**

```typescript
// New refactored backend is now default (Phase 1-8 complete)
// Set USE_OLD_BACKEND=1 to use legacy backend if issues arise
const backendModule = process.env.USE_OLD_BACKEND === '1' ? 'isi_control.main' : 'src.main'
mainLogger.info(`Using backend module: ${backendModule} ${process.env.USE_OLD_BACKEND === '1' ? '(LEGACY)' : '(REFACTORED)'}`)

const poetryArgs = [...poetryCommandArgs, 'run', 'python', '-u', '-m', backendModule]
```

**Why this change?**
- New backend becomes default
- Old backend available as fallback via `USE_OLD_BACKEND=1`
- Clear indication in logs which backend is running

---

## Step 5: Remove Old Backend (Future)

After 90 days of successful operation with new backend:

1. **Backup old code:**
   ```bash
   cd /Users/Adam/KimLabISI/apps/backend
   tar -czf ~/.backup/isi_control_old_$(date +%Y%m%d).tar.gz src/isi_control/
   ```

2. **Remove old backend:**
   ```bash
   rm -rf src/isi_control/
   ```

3. **Update electron main.ts:**
   ```typescript
   // Remove dual-boot support, use new backend only
   const poetryArgs = [...poetryCommandArgs, 'run', 'python', '-u', '-m', 'src.main']
   ```

4. **Update pyproject.toml:**
   ```toml
   [tool.poetry.scripts]
   isi-macroscope = "src.main:main"  # Remove old entry point
   ```

---

## Emergency Rollback Procedures

### Immediate Rollback (During Testing)

If issues found during testing:

```bash
# Option 1: Environment variable (quickest)
unset USE_NEW_BACKEND
npm run dev

# Option 2: Revert main.ts changes
git checkout apps/desktop/src/electron/main.ts
npm run dev
```

### Post-Deployment Rollback

If issues found after making new backend default:

```bash
# Set environment variable
export USE_OLD_BACKEND=1
npm run dev

# Or revert git commit
git revert <commit-hash-of-backend-switch>
```

---

## Known Differences (None Expected)

The new backend is 100% backward compatible. However, document any differences found:

### Performance
- [ ] Startup time: _____ (old) vs _____ (new)
- [ ] Frame rate: _____ (old) vs _____ (new)
- [ ] Memory usage: _____ (old) vs _____ (new)

### Behavior
- [ ] Any command response format changes?
- [ ] Any timing differences?
- [ ] Any error message differences?

---

## Troubleshooting

### Issue: "Backend failed to reach ready state within 15 seconds"

**Possible causes:**
- New backend takes longer to import (more modules)
- Configuration file issues
- Missing dependencies

**Solution:**
```bash
# Test backend directly
cd /Users/Adam/KimLabISI/apps/backend
.venv/bin/python src/main.py

# Check logs for import errors
```

### Issue: "Unknown command type: xxx"

**Possible causes:**
- Handler mapping in new backend missing a command

**Solution:**
- Check `src/main.py` create_handlers() function
- Verify all 26 commands are mapped
- Compare with old backend handlers

### Issue: "Shared memory frame reading failed"

**Possible causes:**
- Shared memory path changed
- Buffer size mismatch

**Solution:**
- Check shared memory configuration in `src/main.py`
- Verify buffer sizes match frontend expectations

### Issue: Frontend shows "Backend error: ModuleNotFoundError"

**Possible causes:**
- Virtual environment not activated
- Dependencies not installed

**Solution:**
```bash
cd /Users/Adam/KimLabISI/apps/backend
.venv/bin/python -m pip install -e .
```

---

## Success Criteria

Mark as **MIGRATION COMPLETE** when:

- ✅ All integration tests passing with new backend
- ✅ No regressions in functionality
- ✅ Performance equal or better than old backend
- ✅ No errors in logs after 1 hour of operation
- ✅ All team members trained on rollback procedure
- ✅ Tested on all target platforms (macOS, Linux, Windows if applicable)

---

## Timeline Recommendation

| Phase | Duration | Description |
|-------|----------|-------------|
| **1. Preparation** | 1 day | Update main.ts with dual-boot, test compilation |
| **2. Initial Testing** | 2-3 days | Test new backend with frontend, document differences |
| **3. Comparison Testing** | 3-5 days | Run side-by-side tests, validate identical behavior |
| **4. Beta Testing** | 1-2 weeks | Use new backend for daily work, collect feedback |
| **5. Make Default** | 1 day | Switch default to new backend |
| **6. Monitoring** | 1 month | Monitor production use, keep old backend available |
| **7. Deprecation** | 90 days | Remove old backend after successful operation |

**Total:** ~4 months from start to old backend removal

---

## Contact / Support

**If issues arise:**
1. Check this guide's troubleshooting section
2. Review logs in `apps/backend/logs/isi_macroscope.log`
3. Run `apps/backend/src/test_all.py` to verify backend health
4. Rollback to old backend if critical issues found
5. Document issues in GitHub issues with "backend-migration" label

---

## Appendix: IPC Command Reference

### Commands New Backend Must Support (26 total)

**Camera Commands (6):**
- `detect_cameras`
- `get_camera_capabilities`
- `start_camera_acquisition`
- `stop_camera_acquisition`
- `get_camera_histogram`
- `get_synchronization_data`

**Acquisition Commands (4):**
- `start_acquisition`
- `stop_acquisition`
- `get_acquisition_status`
- `set_acquisition_mode`

**Playback Commands (5):**
- `list_sessions`
- `load_session`
- `get_session_data`
- `unload_session`
- `get_playback_frame`

**Analysis Commands (3):**
- `start_analysis`
- `stop_analysis`
- `get_analysis_status`

**Parameter Commands (5):**
- `get_all_parameters`
- `get_parameter_group`
- `update_parameter_group`
- `reset_to_defaults`
- `get_parameter_info`

**System Commands (3):**
- `ping`
- `get_system_status`
- `health_check`

All 26 commands are implemented in `apps/backend/src/main.py` create_handlers() function.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-10
**Status:** Ready for Implementation
