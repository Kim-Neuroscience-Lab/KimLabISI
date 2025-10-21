# KimLabISI

[![License](https://img.shields.io/github/license/Kim-Neuroscience-Lab/KimLabISI)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-pylint-black)](https://pylint.pycqa.org)
[![Code Style](https://img.shields.io/badge/code%20style-ESLint-4B32C3)](https://eslint.org)
[![Contributors](https://img.shields.io/github/contributors/Kim-Neuroscience-Lab/KimLabISI)](https://github.com/Kim-Neuroscience-Lab/KimLabISI/graphs/contributors)
[![Lines of Code](https://tokei.rs/b1/github/Kim-Neuroscience-Lab/KimLabISI?category=code)](https://github.com/Kim-Neuroscience-Lab/KimLabISI)

> GPU-accelerated intrinsic signal imaging system for retinotopic mapping in visual neuroscience research.

---

## Quick Links

- **[Documentation Hub](docs/README.md)** - Complete system documentation
- **[Getting Started](docs/guides/getting-started.md)** - Installation and setup
- **[Testing Guide](docs/guides/testing.md)** - Testing procedures
- **[Changelog](docs/CHANGELOG.md)** - Recent changes and updates

---

## System Overview

KimLabISI is a desktop application for real-time intrinsic signal imaging (ISI) acquisition and analysis. It enables researchers to map visual cortex retinotopy using the Kalatsky-Stryker Fourier-based method.

### Key Features

- **Real-Time Acquisition**: GPU-accelerated stimulus generation with VSync-locked playback
- **Retinotopic Analysis**: Altitude, azimuth, and visual field sign mapping
- **Multi-Mode Operation**: Preview, record, and playback modes
- **Cross-Platform**: Electron + Python backend architecture

### Architecture

```
KimLabISI/
├── apps/
│   ├── backend/           # Python backend (acquisition, analysis, stimulus)
│   └── desktop/           # Electron frontend (React + TypeScript)
├── docs/                  # Living documentation
│   ├── components/        # Component reference docs
│   ├── decisions/         # Architecture Decision Records
│   ├── guides/            # User and developer guides
│   ├── investigations/    # Technical investigations
│   └── archive/           # Historical documents
└── scripts/               # Development and deployment scripts
```

---

## Documentation

### For Users

- **[Getting Started Guide](docs/guides/getting-started.md)** - Installation, setup, and first run
- **[Testing Guide](docs/guides/testing.md)** - Quick tests and troubleshooting
- **[Changelog](docs/CHANGELOG.md)** - Recent changes and updates

### For Developers

- **[Architecture Overview](docs/README.md)** - System architecture and design
- **[Component Docs](docs/components/)** - Detailed component documentation
  - [Acquisition System](docs/components/acquisition-system.md)
  - [Stimulus System](docs/components/stimulus-system.md)
  - [Analysis Pipeline](docs/components/analysis-pipeline.md)
  - [Parameter Manager](docs/components/parameter-manager.md)
- **[Architecture Decisions](docs/decisions/)** - ADRs documenting major decisions
  - [ADR-006: Unified Logging](docs/decisions/006-unified-logging.md) - Console output standards
  - [ADR-005: No Legacy Code](docs/decisions/005-no-legacy-code-policy.md)
  - [ADR-004: Parameter Manager](docs/decisions/004-parameter-manager-refactor.md)
- **[Logging Architecture](docs/architecture/logging.md)** - Unified logging standards
- **[Known Issues](docs/known-issues/)** - Tracked bugs and feature requests

---

## Technology Stack

### Backend (Python)
- **Camera**: spinnaker_python (FLIR Blackfly S), OpenCV (cv2)
- **Stimulus**: ModernGL (GPU-accelerated OpenGL)
- **Analysis**: NumPy, SciPy, OpenCV (colormapping and rendering)
- **IPC**: ZeroMQ + Shared Memory

### Frontend (TypeScript)
- **Framework**: Electron + React
- **UI**: Tailwind CSS
- **State**: React Context + Hooks
- **Build**: Vite

---

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Kim-Neuroscience-Lab/KimLabISI.git
   cd KimLabISI
   ```

2. **Run setup script**:
   ```bash
   ./setup_and_run.sh
   ```

3. **Open the application** - Electron window launches automatically

For detailed setup instructions, see the [Getting Started Guide](docs/guides/getting-started.md).

---

## Development

### Project Structure

- `apps/backend/` - Python backend
  - `src/acquisition/` - Acquisition modes and control
  - `src/camera/` - Camera hardware interface
  - `src/analysis/` - Retinotopic analysis pipeline
  - `src/stimulus/` - GPU stimulus generation
  - `src/parameters/` - Configuration management
  - `src/ipc/` - Inter-process communication

- `apps/desktop/` - Electron frontend
  - `src/components/` - React components
  - `src/electron/` - Electron main process
  - `src/hooks/` - Custom React hooks

### Key Commands

```bash
# Backend (Python)
cd apps/backend
poetry install
poetry run python src/main.py

# Frontend (Electron)
cd apps/desktop
npm install
npm run dev

# Full stack
./setup_and_run.sh
```

---

## Contributing

1. Read the [Architecture Overview](docs/README.md)
2. Review [Architecture Decisions](docs/decisions/)
3. Check [Known Issues](docs/known-issues/) for open tasks
4. Follow existing code style (pylint + ESLint)
5. Update documentation for significant changes

---

## License

See [LICENSE](LICENSE) file for details.

---

## References

- **Kalatsky & Stryker (2003)**: Fourier-based retinotopic mapping method
- **Juavinett et al. (2017)**: Visual field sign analysis for area boundaries
- **Zhuang et al. (2017)**: retinotopic_mapping Python package
