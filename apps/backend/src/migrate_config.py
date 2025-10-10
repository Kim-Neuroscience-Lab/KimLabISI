#!/usr/bin/env python3
"""Phase 8: Configuration Migration Utility.

This utility helps migrate from the old configuration format (if different)
to the new AppConfig format used by the refactored backend.

The current system uses the same JSON format, so this mainly serves as:
1. Validation tool for configuration files
2. Backup/restore utility
3. Configuration converter for future format changes

Run with: python src/migrate_config.py [--validate | --backup | --restore]
"""

import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import AppConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigMigrator:
    """Configuration migration and validation utility."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_file = config_dir / "isi_parameters.json"
        self.backup_dir = config_dir / "backups"

    def validate_config(self, config_path: Optional[Path] = None) -> bool:
        """Validate configuration file can be loaded.

        Args:
            config_path: Optional path to config file (defaults to main config)

        Returns:
            True if config is valid
        """
        if config_path is None:
            config_path = self.config_file

        logger.info(f"Validating configuration: {config_path}")

        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return False

        try:
            # Try to load as JSON first
            with open(config_path) as f:
                data = json.load(f)

            logger.info("  JSON parsing: OK")

            # Verify required top-level structure
            if "current" not in data:
                logger.error("  Missing 'current' section in config")
                return False

            logger.info("  Structure check: OK")

            # Try to load with AppConfig
            config = AppConfig.from_file(str(config_path))
            logger.info("  AppConfig loading: OK")

            # Verify all sections loaded
            sections = [
                "ipc", "shared_memory", "camera", "monitor", "stimulus",
                "acquisition", "analysis", "session", "parameters", "logging"
            ]

            for section in sections:
                if not hasattr(config, section):
                    logger.error(f"  Missing section: {section}")
                    return False

            logger.info("  All sections present: OK")

            # Print summary
            logger.info("\nConfiguration Summary:")
            logger.info(f"  IPC Health Port: {config.ipc.health_port}")
            logger.info(f"  IPC Sync Port: {config.ipc.sync_port}")
            logger.info(f"  Shared Memory Stream: {config.shared_memory.stream_name}")
            logger.info(f"  Selected Camera: {config.camera.selected_camera or 'None'}")
            logger.info(f"  Selected Display: {config.monitor.selected_display or 'None'}")
            logger.info(f"  Acquisition Directions: {', '.join(config.acquisition.directions)}")
            logger.info(f"  Acquisition Cycles: {config.acquisition.cycles}")

            logger.info("\nConfiguration is VALID")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"  JSON parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"  Validation error: {e}")
            return False

    def backup_config(self, label: Optional[str] = None) -> Optional[Path]:
        """Create backup of current configuration.

        Args:
            label: Optional label for backup (defaults to timestamp)

        Returns:
            Path to backup file, or None if backup failed
        """
        if not self.config_file.exists():
            logger.error(f"Configuration file not found: {self.config_file}")
            return None

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if label:
            backup_name = f"isi_parameters_{label}_{timestamp}.json"
        else:
            backup_name = f"isi_parameters_backup_{timestamp}.json"

        backup_path = self.backup_dir / backup_name

        try:
            # Copy config file
            shutil.copy2(self.config_file, backup_path)
            logger.info(f"Configuration backed up to: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    def list_backups(self) -> list[Path]:
        """List all available configuration backups.

        Returns:
            List of backup file paths, sorted by modification time (newest first)
        """
        if not self.backup_dir.exists():
            return []

        backups = list(self.backup_dir.glob("isi_parameters*.json"))
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        return backups

    def restore_config(self, backup_path: Optional[Path] = None) -> bool:
        """Restore configuration from backup.

        Args:
            backup_path: Path to backup file (defaults to most recent)

        Returns:
            True if restore successful
        """
        # If no backup specified, use most recent
        if backup_path is None:
            backups = self.list_backups()
            if not backups:
                logger.error("No backups found")
                return False
            backup_path = backups[0]
            logger.info(f"Using most recent backup: {backup_path}")

        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        # Validate backup before restoring
        if not self.validate_config(backup_path):
            logger.error("Backup validation failed - not restoring")
            return False

        try:
            # Create backup of current config first
            if self.config_file.exists():
                logger.info("Creating backup of current configuration...")
                self.backup_config(label="pre_restore")

            # Restore from backup
            shutil.copy2(backup_path, self.config_file)
            logger.info(f"Configuration restored from: {backup_path}")

            # Validate restored config
            if self.validate_config():
                logger.info("Restored configuration is valid")
                return True
            else:
                logger.error("Restored configuration failed validation")
                return False

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def convert_legacy_format(self, legacy_path: Path, output_path: Path) -> bool:
        """Convert legacy configuration format to new format.

        This is a placeholder for future format changes. Currently,
        the format hasn't changed, so this just validates and copies.

        Args:
            legacy_path: Path to legacy config file
            output_path: Path for converted config file

        Returns:
            True if conversion successful
        """
        logger.info(f"Converting configuration format...")
        logger.info(f"  From: {legacy_path}")
        logger.info(f"  To: {output_path}")

        if not legacy_path.exists():
            logger.error(f"Legacy config not found: {legacy_path}")
            return False

        try:
            # Load legacy config
            with open(legacy_path) as f:
                legacy_data = json.load(f)

            # In the current implementation, format is the same
            # Future versions may need actual conversion logic here
            converted_data = legacy_data

            # Write converted config
            with open(output_path, 'w') as f:
                json.dump(converted_data, f, indent=2)

            logger.info("Conversion complete")

            # Validate converted config
            return self.validate_config(output_path)

        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return False

    def show_backup_list(self):
        """Display list of available backups."""
        backups = self.list_backups()

        if not backups:
            logger.info("No configuration backups found")
            return

        logger.info(f"\nAvailable Configuration Backups ({len(backups)}):")
        logger.info("-" * 80)

        for i, backup in enumerate(backups, 1):
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            size = backup.stat().st_size
            logger.info(f"{i:2d}. {backup.name}")
            logger.info(f"    Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"    Size: {size:,} bytes")

        logger.info("-" * 80)


def main():
    """Main entry point for migration utility."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ISI Macroscope Configuration Migration Utility"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate current configuration"
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup of current configuration"
    )

    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore configuration from backup"
    )

    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available configuration backups"
    )

    parser.add_argument(
        "--backup-file",
        type=Path,
        help="Specific backup file to restore from"
    )

    parser.add_argument(
        "--label",
        type=str,
        help="Label for backup (e.g., 'before_upgrade')"
    )

    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Configuration directory (defaults to ../config)"
    )

    args = parser.parse_args()

    # Determine config directory
    if args.config_dir:
        config_dir = args.config_dir
    else:
        config_dir = Path(__file__).parent.parent / "config"

    migrator = ConfigMigrator(config_dir)

    # Execute requested operation
    success = True

    if args.validate:
        logger.info("=" * 80)
        logger.info("CONFIGURATION VALIDATION")
        logger.info("=" * 80)
        success = migrator.validate_config()

    elif args.backup:
        logger.info("=" * 80)
        logger.info("CONFIGURATION BACKUP")
        logger.info("=" * 80)
        backup_path = migrator.backup_config(label=args.label)
        success = backup_path is not None

    elif args.restore:
        logger.info("=" * 80)
        logger.info("CONFIGURATION RESTORE")
        logger.info("=" * 80)
        success = migrator.restore_config(backup_path=args.backup_file)

    elif args.list_backups:
        logger.info("=" * 80)
        logger.info("CONFIGURATION BACKUPS")
        logger.info("=" * 80)
        migrator.show_backup_list()

    else:
        # No operation specified - show help
        parser.print_help()
        logger.info("\nExamples:")
        logger.info("  Validate config:  python src/migrate_config.py --validate")
        logger.info("  Create backup:    python src/migrate_config.py --backup --label my_backup")
        logger.info("  List backups:     python src/migrate_config.py --list-backups")
        logger.info("  Restore backup:   python src/migrate_config.py --restore")
        return

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
