# Documentation Migration - File Categorization

**Date**: 2025-10-14
**Purpose**: Categorize all 43 scattered .md files for migration to new docs structure

---

## Summary

**Total Files**: 43 scattered documentation files
**Action Categories**:
- **Archive (28 files)**: Historical reports, completed fixes
- **Convert to ADR (4 files)**: Architectural decisions
- **Convert to Investigation (3 files)**: Active technical investigations
- **Consolidate to Living Docs (8 files)**: Merge into component docs

---

## Category 1: Archive Immediately (28 files)

These are completed work that should be moved to `docs/archive/2025-10-14/` with timestamp prefixes in filename format: `YYYYMMDD_HHMM_ORIGINALNAME.md`

**Example**: `ACQUISITION_SYSTEM_AUDIT_REPORT.md` (2025-10-13 19:32) → `20251013_1932_ACQUISITION_SYSTEM_AUDIT_REPORT.md`

### Root Directory (12 files → archive)
1. `ACQUISITION_SYSTEM_AUDIT_REPORT.md` (2025-10-13 19:32) → Archive (covered in components/acquisition-system.md)
2. `ACQUISITION_VIEWPORT_AUDIT_REPORT.md` (2025-10-13 00:07) → Archive (investigation complete)
3. `CRITICAL_INTEGRATION_ISSUES_REPORT.md` (2025-10-14 17:13) → Convert to Investigation (2025-10/20251014_critical_integration_issues.md)
4. `STIMULUS_INTEGRATION_FIX_COMPLETE.md` (2025-10-14 14:42) → Archive
5. `STIMULUS_INTEGRATION_INVESTIGATION_REPORT.md` (2025-10-14 14:40) → Archive
6. `UNIFIED_ACQUISITION_ARCHITECTURE_AUDIT.md` (2025-10-14 09:30) → Archive
7. `UNIFIED_ACQUISITION_ARCHITECTURE_COMPLETE.md` (2025-10-14 10:00) → Archive
8. `UNIFIED_STIMULUS_INTEGRITY_AUDIT.md` (2025-10-14 10:15) → Archive
9. `UNIFIED_STIMULUS_MIGRATION_AUDIT.md` (2025-10-14 13:26) → Archive
10. `UNIFIED_STIMULUS_QUICK_REFERENCE.md` (2025-10-14 10:01) → Consolidate into components/stimulus-system.md
11. `QUICK_START_TESTING_GUIDE.md` (2025-10-14 14:43) → Move to guides/testing.md
12. `SYNC_LOGGING_FIX_COMPLETE.md` (2025-10-14 17:14) → Archive (completed 2025-10-14)

### apps/backend (16 files → archive or convert)
1. `BACKEND_ARCHITECTURE_AUDIT.md` (2025-10-12 23:22) → Archive (covered in ADR-001)
2. `COMPREHENSIVE_AUDIT_RESPONSE.md` (2025-10-12 16:10) → Archive
3. `CORRECTION_COMPLETE_SUMMARY.md` (2025-10-12 12:37) → Archive
4. `DEFINITIVE_ANSWER.md` (2025-10-12 12:20) → Archive
5. `DIRECTION_MAPPING_FIX_COMPLETE.md` (2025-10-12 15:44) → Archive (covered in CHANGELOG)
6. `MATLAB_BIDIRECTIONAL_ANALYSIS.md` (2025-10-12 02:15) → Archive (reference material)
7. `PARAMETER_MANAGER_REFACTOR_COMPLETE.md` (2025-10-12 23:50) → Convert to ADR-004
8. `PARAMETER_MANAGER_REFACTOR_STATUS.md` (2025-10-12 23:40) → Archive (superseded by COMPLETE)
9. `PARAMETER_UPDATE_SUMMARY.md` (2025-10-12 11:25) → Archive
10. `PIPELINE_COMPARISON.md` (2025-10-12 10:42) → Archive (reference material)
11. `PIPELINE_DIFFERENCES.md` (2025-10-12 14:35) → Archive
12. `PIPELINE_NOW_MATCHES_OLD_IMPLEMENTATION.md` (2025-10-12 14:36) → Archive
13. `SAMPLE_DATA_ANALYSIS_FINAL_REPORT.md` (2025-10-12 12:11) → Archive (reference material)
14. `SAMPLE_DATA_STRUCTURE_DISCOVERY.md` (2025-10-12 12:09) → Archive (reference material)
15. `LITERATURE_DEFAULTS.md` (2025-10-12 11:24) → Consolidate into components/analysis-pipeline.md
16. `STARTUP_PERFORMANCE_OPTIMIZATION_REPORT.md` (2025-10-13 08:39) → Archive (covered in CHANGELOG)

---

## Category 2: Convert to ADRs (4 files)

These document architectural decisions and should become ADRs:

1. **`apps/backend/PARAMETER_MANAGER_REFACTOR_COMPLETE.md`** (2025-10-12 23:50)
   - Target: `docs/decisions/004-parameter-manager-refactor.md`
   - Status: Accepted (implemented 2025-10-11)
   - Original date: 2025-10-12 23:50
   - Key decision: Move parameter manager to dedicated module

2. **`apps/backend/UNIFIED_STIMULUS_INTEGRATION_PLAN.md`** (2025-10-14 10:36) + **`UNIFIED_STIMULUS_FIXES_COMPLETE.md`** (2025-10-14 10:37)
   - Target: `docs/decisions/002-unified-stimulus-controller.md`
   - Status: Accepted (implemented 2025-10-10)
   - Original dates: 2025-10-14 10:36-10:37
   - Key decision: Single controller for preview and record modes

3. **`apps/backend/BACKEND_ARCHITECTURE_AUDIT.md`** (2025-10-12 23:22) (partial)
   - Target: `docs/decisions/001-backend-modular-architecture.md`
   - Status: Accepted (implemented 2025-10-10)
   - Original date: 2025-10-12 23:22
   - Key decision: Reorganize src/isi_control/ into modular structure

4. **Analysis Rendering Decision** (inferred from docs/archive/20251009_ANALYSIS_RENDERING_REFACTOR_COMPLETE.md)
   - Target: `docs/decisions/003-backend-rendering.md`
   - Status: Accepted (implemented 2025-10-09)
   - Original date: 2025-10-09
   - Key decision: Render matplotlib figures in backend vs frontend

---

## Category 3: Convert to Investigations (3 files)

Active or resolved technical investigations:

1. **`CRITICAL_INTEGRATION_ISSUES_REPORT.md`** (2025-10-14 17:13)
   - Target: `docs/investigations/resolved/2025-10/20251014_critical_integration_issues.md`
   - Status: Resolved 2025-10-14 17:13
   - Original date: 2025-10-14 17:13
   - Root cause: SYNC logging spam + unclear errors

2. **VFS Pipeline Fixes** (consolidate multiple files, 2025-10-12 13:48 - 15:56)
   - Source files:
     - `apps/backend/VFS_PIPELINE_FIXES_MASTER_REPORT.md` (2025-10-12 15:56) - Master report
     - `apps/backend/VFS_COMPLETE_FIX_SUMMARY.md` (2025-10-12 14:15) - Summary
     - `apps/backend/VFS_FIX_IMPLEMENTATION_SUMMARY.md` (2025-10-12 13:51) - Implementation
     - `apps/backend/VFS_PROCESSING_COMPARISON.md` (2025-10-12 13:48) - Comparison
     - `apps/backend/STATISTICAL_VFS_FIX_COMPLETE.md` (2025-10-12 15:55) - Statistical fix
   - Target: `docs/investigations/resolved/2025-10/20251012_vfs_pipeline_fixes.md`
   - Status: Resolved 2025-10-12 (investigation spanned 13:48 - 15:56)
   - Original dates: 2025-10-12 13:48 - 15:56
   - Root cause: Phase wrapping + incorrect statistical masking

3. **Acquisition Viewport Diagnosis** (current work, 2025-10-14 14:12 - 16:25)
   - Source files:
     - `apps/backend/PREVIEW_RECORD_DIAGNOSTIC.md` (2025-10-14 16:19) - Diagnostic analysis
     - `apps/backend/PLAYBACK_ALREADY_RUNNING_FIX.md` (2025-10-14 16:02) - First fix
     - `apps/backend/PREVIEW_AUTO_GENERATION_FIX_COMPLETE.md` (2025-10-14 16:25) - Auto-gen fix
     - `apps/backend/PREVIEW_RECORD_MODE_FIX_COMPLETE.md` (2025-10-14 15:11) - Mode fix
     - `apps/backend/STIMULUS_PERSISTENCE_FIX_COMPLETE.md` (2025-10-14 14:12) - Persistence fix
   - Target: `docs/investigations/active/acquisition-viewport-diagnosis.md`
   - Status: Active (user testing needed)
   - Original dates: 2025-10-14 14:12 - 16:25 (ongoing)
   - Current hypotheses: Multiple issues diagnosed and fixed

---

## Category 4: Consolidate to Living Docs (8 files)

Extract content into component documentation:

### Target: `docs/components/acquisition-system.md`
- Source: `ACQUISITION_SYSTEM_AUDIT_REPORT.md`
- Source: `UNIFIED_ACQUISITION_ARCHITECTURE_COMPLETE.md`
- Source: `ACQUISITION_VIEWPORT_AUDIT_REPORT.md` (partial - UI details)

### Target: `docs/components/stimulus-system.md`
- Source: `UNIFIED_STIMULUS_QUICK_REFERENCE.md`
- Source: `apps/backend/STIMULUS_PERSISTENCE_FIX_COMPLETE.md`
- Source: `UNIFIED_STIMULUS_INTEGRITY_AUDIT.md` (partial)

### Target: `docs/components/analysis-pipeline.md`
- Source: `apps/backend/LITERATURE_DEFAULTS.md`
- Source: `apps/backend/MATLAB_BIDIRECTIONAL_ANALYSIS.md` (reference section)
- Source: VFS reports (algorithm details)

### Target: `docs/components/parameter-manager.md`
- Source: `apps/backend/PARAMETER_UPDATE_SUMMARY.md` (recent changes section)

### Target: `docs/guides/testing.md`
- Source: `QUICK_START_TESTING_GUIDE.md`

---

## Category 5: Keep in Place (2 files)

These files should stay where they are:

1. **`README.md` (root)** - Project README, keep in root
2. **`apps/backend/README.md`** - Backend-specific README, keep
3. **`apps/desktop/README.md`** - Frontend-specific README, keep
4. **`apps/desktop/FRONTEND_SHARED_MEMORY_TODO.md`** - Active TODO, convert to investigation or known issue

---

## Migration Actions Summary

| Action | File Count | Destination |
|--------|-----------|-------------|
| Archive | 28 | `docs/archive/2025-10-14/` |
| Convert to ADR | 4 → 4 ADRs | `docs/decisions/` |
| Convert to Investigation | 12 → 3 investigations | `docs/investigations/` |
| Consolidate to Living Docs | 8 | `docs/components/`, `docs/guides/` |
| Keep in place | 4 | Root and app directories |
| **Total** | **43** | - |

---

## Next Steps (Phase 3-6)

1. **Phase 3**: Create living documents by consolidating 8 files
2. **Phase 4**: Create 4 ADRs from architectural decision reports
3. **Phase 5**: Archive 28 completed/obsolete files
4. **Phase 6**: Create 3 investigation documents (2 resolved, 1 active)

---

**Categorization Version**: 1.0
**Date**: 2025-10-14
