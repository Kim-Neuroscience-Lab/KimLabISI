#!/usr/bin/env python3
"""
Startup script for ISI Macroscope Backend
Handles proper module imports and initialization
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

# Now import and run the main module
from isi_control.main import main, ISIMacroscopeBackend

if __name__ == '__main__':
    # Run the main function if it exists, otherwise create backend instance
    if hasattr(sys.modules['isi_control.main'], 'main'):
        sys.modules['isi_control.main'].main()
    else:
        # Parse arguments
        import argparse
        parser = argparse.ArgumentParser(description='ISI Macroscope Control System Backend')
        parser.add_argument('--dev', action='store_true', help='Run in development mode')
        parser.add_argument('--port', type=int, default=8765, help='WebSocket server port')
        args = parser.parse_args()

        # Create and run backend
        backend = ISIMacroscopeBackend(dev_mode=args.dev, port=args.port)
        backend.run()