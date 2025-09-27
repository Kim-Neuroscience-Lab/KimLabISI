# ISI Minimal - Functional ISI Macroscope Control System

Minimal but fully functional implementation of the ISI (Intrinsic Signal Imaging) Macroscope Control System for retinotopic mapping of mouse visual cortex.

## Quick Start

```bash
# Install dependencies
poetry install

# Test the system
poetry run python backend/isi_system.py
```

## Components

- `backend/isi_system.py` - Main system controller
- `backend/hardware_mock.py` - Mock hardware for development
- `backend/isi_analysis.py` - Analysis pipeline (coming soon)
- `backend/simple_server.py` - WebSocket server (coming soon)