/**
 * Centralized logging utility for ISI Control System
 * Replaces scattered console.log statements with structured logging
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

interface LoggerConfig {
  level: LogLevel
  prefix?: string
  timestamp?: boolean
}

class Logger {
  private config: LoggerConfig

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = {
      // Default to WARN to match backend logging configuration
      // Only show warnings and errors by default - reduces console clutter
      level: config.level ?? LogLevel.WARN,
      prefix: config.prefix,
      timestamp: config.timestamp ?? true,
    }
  }

  private formatMessage(level: string, message: string, ...args: unknown[]): [string, ...unknown[]] {
    const parts: string[] = []

    if (this.config.timestamp) {
      parts.push(`[${new Date().toISOString()}]`)
    }

    parts.push(`[${level}]`)

    if (this.config.prefix) {
      parts.push(`[${this.config.prefix}]`)
    }

    return [parts.join(' ') + ' ' + message, ...args]
  }

  debug(message: string, ...args: unknown[]): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.log(...this.formatMessage('DEBUG', message, ...args))
    }
  }

  info(message: string, ...args: unknown[]): void {
    if (this.config.level <= LogLevel.INFO) {
      console.info(...this.formatMessage('INFO', message, ...args))
    }
  }

  warn(message: string, ...args: unknown[]): void {
    if (this.config.level <= LogLevel.WARN) {
      console.warn(...this.formatMessage('WARN', message, ...args))
    }
  }

  error(message: string, ...args: unknown[]): void {
    if (this.config.level <= LogLevel.ERROR) {
      console.error(...this.formatMessage('ERROR', message, ...args))
    }
  }

  /**
   * Create a child logger with a specific prefix
   */
  child(prefix: string): Logger {
    return new Logger({
      ...this.config,
      prefix: this.config.prefix ? `${this.config.prefix}:${prefix}` : prefix,
    })
  }
}

// Default logger instance
export const logger = new Logger()

// Module-specific loggers
export const mainLogger = logger.child('Main')
export const ipcLogger = logger.child('IPC')
export const hookLogger = logger.child('Hook')
export const componentLogger = logger.child('Component')
