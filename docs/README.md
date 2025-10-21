# ISI Macroscope Documentation

**Last Updated**: 2025-10-14
**Project**: KimLabISI - Intrinsic Signal Imaging Control System

> Comprehensive documentation for the ISI Macroscope control system, including architecture, component details, guides, and decision records.

---

## Quick Links

- **Recent changes?** → [Changelog](changes/CHANGELOG.md)
- **System architecture?** → [Architecture Overview](architecture/README.md)
- **Troubleshooting?** → [Troubleshooting Guide](guides/troubleshooting.md)
- **Architecture decisions?** → [Architecture Decision Records](adr/README.md)
- **Active audits?** → [Audits](audits/)

---

## General Notes

- \*_Always use real date and time stamps_ when making new incrimental status update or audit files or updating living documents and properly organize the files in the `audits/`, `changes/`, `adr/`, etc. directories.
- When making a change, update the CHANGELOG.md([CHANGELOG.md](changes/CHANGELOG.md)) following the usage guidelines in the [CHANGELOG.md](changes/CHANGELOG.md) file.
- When adding todo items, update the TODO.md([TODO.md](TODO.md)) following the usage guidelines in the [TODO.md](TODO.md) file.
- When writing an audit, the audit file should be named with the timestamp in the filename format: `YYYY-MM-DD-HHMM_ORIGINALNAME.md` and placed in the `audits/` directory.

## Documentation Structure

### 📐 Architecture

High-level system design and architectural decisions:

- [Architecture Overview](architecture/README.md) - System design philosophy and patterns
- [Logging Architecture](architecture/logging.md) - Unified logging across backend and frontend

### 🔧 Components

Deep-dives into each major component:

- [Acquisition System](components/acquisition-system.md) - Camera-triggered acquisition
- [Analysis Pipeline](components/analysis-pipeline.md) - ISI analysis algorithms
- [Camera System](components/camera-system.md) - Camera control and frame capture
- [Stimulus System](components/stimulus-system.md) - Stimulus generation and playback
- [Parameter Manager](components/parameter-manager.md) - Configuration management
- [Shared Memory](components/data-recording.md) - Data recording

### 📋 Architecture Decision Records (ADRs)

Documented architectural decisions with rationale:

- [ADR Index](adr/README.md) - All ADRs with status
- [ADR Template](adr/template.md) - Template for new ADRs

### 🔍 Audits

Active and resolved technical audits:

- [Active Audits](audits/)

When documenting an audit, place the md file in the `audits/` directory with the timestamp in the filename format: `YYYY-MM-DD-HHMM_ORIGINALNAME.md`

### 📝 Changes

- [Change log](changes/CHANGELOG.md) - Living change log

### 📚 References

Scientific papers and external documentation:

- [Reference Index](references/) - All references

### 🗄️ Archive

Historical documentation (read-only):

- [Archive Index](archive/) - Archived documents by date

Should be named with the timestamp in the filename format: `YYYY-MM-DD-HHMM_ORIGINALNAME.md`
