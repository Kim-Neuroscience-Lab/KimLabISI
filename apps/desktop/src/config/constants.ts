/**
 * Centralized configuration constants for ISI Control System
 * Replaces magic numbers scattered throughout the codebase
 */

export const IPC_CONFIG = {
  // Multi-channel IPC ports
  HEALTH_PORT: 5555,
  SYNC_PORT: 5558,
  SHARED_MEMORY_PORT: 5557,

  // Timeouts (milliseconds)
  STARTUP_TIMEOUT: 15000, // 15 seconds
  HEALTH_CHECK_INTERVAL: 5000, // 5 seconds
  PROCESS_KILL_TIMEOUT: 1000, // 1 second for graceful shutdown

  // Cache durations (seconds)
  HARDWARE_DETECTION_CACHE: 30, // 30 seconds
} as const

export const UI_CONFIG = {
  // Window dimensions (percentages of screen size)
  WINDOW_WIDTH_PERCENT: 0.85,
  WINDOW_HEIGHT_PERCENT: 0.9,

  // Minimum window dimensions (percentages)
  MIN_WIDTH_PERCENT: 0.6,
  MIN_HEIGHT_PERCENT: 0.6,

  // Fallback dimensions (pixels)
  MIN_WIDTH_PX: 1200,
  MIN_HEIGHT_PX: 800,
} as const

export const LOGGING_CONFIG = {
  // Log levels
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,

  // Default level based on environment
  DEFAULT_LEVEL: process.env.NODE_ENV === 'development' ? 0 : 1,
} as const

export const PATHS = {
  // Backend paths
  BACKEND_MAIN_MODULE: 'isi_control.main',
  SHARED_MEMORY_PATH: '/tmp/stimulus_stream_shm',

  // Candidate backend root directories
  BACKEND_ROOT_CANDIDATES: [
    '../../backend',
    '../backend',
    '../backend',
    '../../backend',
    '../backend',
    'apps/backend',
  ] as const,
} as const

export const ELECTRON_CONFIG = {
  // Dev tools
  OPEN_DEV_TOOLS_IN_DEVELOPMENT: true,

  // Security
  NODE_INTEGRATION: false,
  CONTEXT_ISOLATION: true,
  WEB_SECURITY: true,
} as const
