# ADR-005: No Legacy Code Policy

**Status**: Accepted
**Date**: 2025-10-15
**Deciders**: Backend Team
**Related**: All Components, [TODO.md](../TODO.md)

---

## Context and Problem Statement

The ISI Macroscope codebase audit (2025-10-14) revealed that **camera-triggered stimulus code** still exists despite documentation claiming it was removed. This represents a critical problem:

```python
# In camera/manager.py - STILL ACTIVE
if self.camera_triggered_stimulus:
    stimulus_frame, stimulus_metadata = (
        self.camera_triggered_stimulus.generate_next_frame()
    )
```

**The system has TWO competing stimulus architectures**:
1. `unified_stimulus` (correct architecture - independent threads)
2. `camera_triggered_stimulus` (old architecture - violates design principles)

This creates:
- **Architectural confusion**: Which path is the "real" implementation?
- **Maintenance burden**: Must maintain two systems instead of one
- **Documentation lies**: Docs claim old code was removed - this is FALSE
- **Testing complexity**: Must test both paths or risk breakage
- **Timing conflicts**: Potential race conditions between competing systems
- **Violation of principles**: Camera-triggered approach breaks independent threads architecture

**We need a clear policy**: Should we keep deprecated/legacy/dead code in the codebase?

## Decision Drivers

- **Code clarity**: Codebase should reflect ONE clear architecture, not multiple competing approaches
- **Maintainability**: Dead code creates maintenance burden and confusion
- **Documentation accuracy**: Code and docs must match reality
- **Testing burden**: Testing multiple deprecated paths wastes resources
- **Scientific validity**: Architectural violations compromise experimental integrity
- **Developer confidence**: Unclear what code is "real" vs "legacy"
- **Technical debt**: Legacy code accumulates and compounds over time

## Options Considered

### Option 1: Keep Legacy Code with Deprecation Comments
**Keep old code "just in case" with comments marking it deprecated.**

**Pros**:
- Easy to revert if new approach fails
- Provides reference for "how it used to work"
- No risk of breaking old functionality

**Cons**:
- Creates architectural confusion (which system is real?)
- Documentation lies (claims code was removed when it wasn't)
- Maintenance burden (must maintain deprecated paths)
- Testing complexity (must test or ignore deprecated code)
- Code bloat (codebase grows but functionality doesn't)
- False sense of safety (deprecated code likely broken anyway)

### Option 2: Comment Out Legacy Code
**Keep old code but commented out "for reference".**

**Pros**:
- Easy to reference old implementation
- No execution overhead

**Cons**:
- Still creates visual clutter
- Comments can drift from reality
- No guarantee commented code still works
- Git history already provides this reference
- Encourages keeping technical debt

### Option 3: Aggressive Deletion Policy (SELECTED)
**Delete all legacy/deprecated/dead code immediately. Use git history for reference.**

**Pros**:
- Codebase reflects ONE clear architecture
- Documentation matches reality
- Reduced maintenance burden
- Simpler testing (only test active code)
- Forces commitment to new architecture
- Git history preserves old code if truly needed

**Cons**:
- Requires confidence in new architecture
- Cannot easily revert (must use git)
- Team must be disciplined about deletion

### Option 4: Feature Flags for Backward Compatibility
**Use feature flags to toggle between old and new implementations.**

**Pros**:
- Can switch back if problems arise
- Users can opt-in to new behavior

**Cons**:
- Exponential complexity (2^N paths to test)
- Feature flags become permanent debt
- Never truly removes legacy code
- Creates confusion about "default" behavior
- NOT applicable here (no backward compatibility requirement)

---

## Decision Outcome

**Chosen Option**: Option 3 - Aggressive Deletion Policy

**Policy**: The ISI Macroscope project **rejects keeping dead, legacy, backward-compatible, deprecated, or architectural debt code** in the codebase.

### Core Principles

1. **One Architecture, One Implementation**
   - If we've moved to a new architecture, DELETE the old one completely
   - No "just in case" safety nets
   - Git history preserves old implementations if truly needed

2. **Documentation Must Match Reality**
   - If docs say code was removed, it MUST be removed
   - Never claim something is gone when it still exists
   - Docs describe ACTUAL behavior, not intended behavior

3. **No Deprecation Period for Internal Code**
   - This is NOT a public API with external users
   - We control all usage of internal code
   - When we refactor, we refactor completely
   - No "deprecated but still works" internal code

4. **Git History is the Archive**
   - Old implementations preserved in git history
   - Use `git log`, `git blame`, `git show` to reference old code
   - No need to keep dead code in HEAD

5. **Force Commitment to New Architecture**
   - Deleting old code forces us to make new architecture work
   - Cannot fall back to broken deprecated code
   - Must fix new architecture properly

### What Gets Deleted

**Delete immediately**:
- Deprecated functions, classes, modules marked as "old" or "legacy"
- Code replaced by new architecture (camera-triggered stimulus)
- Backward compatibility shims for removed features
- Dead code paths never executed
- Commented-out code "for reference"
- Feature flags for deprecated behavior
- Old implementations kept "just in case"

**Keep only if**:
- Code is actively used in current architecture
- Code is scheduled for replacement but replacement not ready
- Code is part of current supported feature set

### Migration Process

When replacing old code with new architecture:

1. **Implement new architecture completely**
   - Ensure new code has feature parity
   - Add comprehensive tests
   - Verify it works in production

2. **Switch ALL usage to new code**
   - Update all call sites
   - No lingering usage of old code
   - Run full test suite

3. **Delete old code immediately**
   - Remove old implementation completely
   - Remove old imports
   - Remove old tests
   - Remove deprecation comments
   - Update documentation

4. **Verify deletion**
   - Use grep to verify no references remain
   - Ensure tests pass
   - Code review confirms complete removal

---

## Implementation: Camera-Triggered Stimulus Removal

**Immediate action required** based on audit findings:

### Files to Delete From

**`apps/backend/src/camera/manager.py`**:
```python
# DELETE line 53
def __init__(
    self,
    param_manager: ParameterManager,
    shared_memory: SharedMemory,
    camera_triggered_stimulus=None,  # ← DELETE THIS
):

# DELETE line 73
self.camera_triggered_stimulus = camera_triggered_stimulus  # ← DELETE THIS

# DELETE lines 696-708 (entire STEP 2 block)
# === STEP 2: TRIGGER STIMULUS GENERATION (CAMERA-TRIGGERED) ===
stimulus_frame = None
stimulus_metadata = None
stimulus_angle = None

if self.camera_triggered_stimulus:
    stimulus_frame, stimulus_metadata = (
        self.camera_triggered_stimulus.generate_next_frame()
    )
# ← DELETE ALL OF THIS

# DELETE lines 741-750 (stimulus event recording)
if self.camera_triggered_stimulus and stimulus_metadata:
    # Record stimulus event
    # ... DELETE THIS BLOCK
```

**`apps/backend/src/main.py`**:
```python
# DELETE any camera_triggered_stimulus instantiation
# DELETE any imports of camera_triggered modules
```

### Verification

After deletion, run:
```bash
cd /Users/Adam/KimLabISI/apps/backend
grep -r "camera_triggered" src/
# Should return ZERO matches

grep -r "CameraTriggeredStimulus" src/
# Should return ZERO matches
```

### Documentation Updates

Update these docs to remove "requires verification" claims:
- `docs/components/camera-system.md` (line 46)
- `docs/components/stimulus-system.md` (line 114)
- `docs/components/acquisition-system.md` (line 133)

Change from:
> "All camera-triggered stimulus code has been removed from codebase (requires verification)"

To:
> "All camera-triggered stimulus code has been removed from codebase (verified 2025-10-15)"

---

## Consequences

### Positive Consequences

✅ **Architectural Clarity**
- Codebase reflects ONE clear architecture
- No confusion about which code path is "real"
- Developers can confidently work with single implementation

✅ **Documentation Accuracy**
- Code matches documentation
- No lies about what was removed
- Trust in documentation increases

✅ **Reduced Maintenance Burden**
- Only maintain active code
- No need to update deprecated code paths
- Simpler refactoring (only one implementation)

✅ **Simpler Testing**
- Test only active code paths
- No need to test deprecated behavior
- Faster test suite

✅ **Forces Architectural Commitment**
- Cannot fall back to broken old code
- Must make new architecture work properly
- Increases quality of new implementation

✅ **Removes Technical Debt**
- Dead code cannot accumulate
- Codebase stays lean
- Easier to understand and navigate

### Negative Consequences

⚠️ **Cannot Easily Revert**
- If new architecture has critical bug, cannot instantly revert
- Must use git to recover old implementation
- Requires re-integration work if reverting

⚠️ **Requires Discipline**
- Team must be disciplined about deleting dead code
- Cannot be lazy and leave "just in case" code
- Requires confidence in new architecture

### Mitigation Strategies

**For "Cannot Easily Revert"**:
- Ensure new architecture is thoroughly tested before deleting old code
- Keep comprehensive test suite
- Document architecture decisions in ADRs (like this one)
- Git history preserves all old implementations

**For "Requires Discipline"**:
- Add deletion checklist to code review process
- Use TODO.md to track legacy code removal tasks
- Run periodic audits (grep for "deprecated", "legacy", "old", etc.)
- Celebrate successful deletions (less code is better!)

### Neutral Consequences

📊 **Git History as Archive**
- Old implementations in git history
- Use `git log -p -- path/to/file` to see old versions
- Use `git show commit:path/to/file` to view old implementation
- No practical difference from keeping dead code in HEAD

---

## Validation

### Success Criteria

✅ **Zero Legacy Code in Main Branch**
- No code marked "deprecated", "legacy", "old"
- No commented-out code "for reference"
- No unused functions/classes/modules

✅ **Documentation Matches Reality**
- If docs say code removed, it MUST be removed
- Run grep to verify claimed deletions

✅ **Single Implementation Per Feature**
- No competing architectures for same functionality
- One clear path through code

✅ **Tests Pass with Single Implementation**
- All tests use active code only
- No tests for deprecated code paths

### Ongoing Validation

**Quarterly Audit** (every 3 months):
```bash
# Search for legacy code markers
grep -r "deprecated" src/
grep -r "legacy" src/
grep -r "old_" src/
grep -r "DEPRECATED" src/
grep -r "TODO.*remove" src/

# Search for commented-out code blocks
grep -r "^[[:space:]]*#.*def " src/
grep -r "^[[:space:]]*#.*class " src/

# Verify no camera-triggered stimulus
grep -r "camera_triggered" src/
```

Expected result: **Zero matches** for all searches.

---

## Exceptions

**The ONLY exception** to this policy:

### Temporary Deprecation During Active Migration

If refactoring a large system:
1. New implementation may coexist with old temporarily
2. Mark old code with `# DEPRECATED - Remove by [DATE]`
3. Add TODO.md entry with deletion deadline
4. Delete by deadline, NO EXTENSIONS

Example:
```python
# DEPRECATED - Remove by 2025-10-20
# Replaced by unified_stimulus architecture
def old_generate_stimulus():
    pass  # Old implementation
```

**Maximum deprecation period**: 1 week
**After deadline**: DELETE regardless of migration status

---

## Related Decisions

- **[ADR-001: Backend Modular Architecture](001-backend-modular-architecture.md)** - Defines clean architecture requiring deletion of old approaches
- **[ADR-002: Unified Stimulus Controller](002-unified-stimulus-controller.md)** - New architecture replacing camera-triggered stimulus
- **[ADR-004: Parameter Manager Refactor](004-parameter-manager-refactor.md)** - Example of complete refactor with old code deletion

---

## References

- **Audit Report**: `docs/audits/2025-10-14_23-50_component_compliance_audit.md`
- **TODO Tracking**: `docs/TODO.md` (ISSUE-001, ISSUE-006, LEGACY-001)
- **Code Location**: `apps/backend/src/camera/manager.py` (lines to delete)

### Relevant Literature

- Martin Fowler: ["Delete Dead Code"](https://martinfowler.com/bliki/DeleteDeadCode.html)
  > "The first step to making code readable is to delete code that isn't read."

- Uncle Bob Martin: "Clean Code"
  > "The ratio of time spent reading versus writing is well over 10 to 1. We are constantly reading old code as part of the effort to write new code. Making it easy to read makes it easier to write."

- Joel Spolsky: "Things You Should Never Do, Part I"
  > "It's important to remember that when you start from scratch... you are throwing away your knowledge."
  > **Note**: We are NOT starting from scratch. We are deleting dead code. Git history preserves knowledge.

---

## Follow-up Tasks

From TODO.md:
- [ ] **ISSUE-001**: Remove camera-triggered stimulus code (deadline: 2025-10-17)
- [ ] **ISSUE-006**: Remove dual stimulus architectures (deadline: 2025-10-17)
- [ ] **LEGACY-001**: Complete removal of camera-triggered stimulus (deadline: 2025-10-17)

After deletion:
- [ ] Run verification grep commands
- [ ] Update documentation to reflect verified removal
- [ ] Update TODO.md resolution history
- [ ] Celebrate reduced codebase size! 🎉

---

**Document Version**: 1.0
**Last Updated**: 2025-10-15
**Policy Status**: Active - applies to all code immediately
