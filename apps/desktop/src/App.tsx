import { useState, useEffect } from 'react'
import ControlPanel from './components/ControlPanel'
import MainViewport from './components/MainViewport'
import Console from './components/Console'
import { useSystemContext } from './context/SystemContext'
import { useParameters } from './hooks/useParameters'
import { componentLogger } from './utils/logger'

function App() {
  const [isExperimentRunning, setIsExperimentRunning] = useState(false)
  const [currentProgress, setCurrentProgress] = useState(0)

  const [, setCurrentSession] = useState<string | null>(null)
  const [logMessages, setLogMessages] = useState<string[]>([])
  const [, setIsControlPanelCollapsed] = useState(false)

  // All parameters managed by backend - no frontend state
  // Hardware lists come from backend parameter manager

  const {
    systemState,
    displayText,
    isReady,
    isError,
    errorMessage,
    connectionError,
    lastControlMessage,
    sendCommand,
    healthSnapshot
  } = useSystemContext()

  const parameterState = useParameters()

  // Use centralized hardware status management
  // Remove hardware status hook - backend will manage all health checking

  // Handle system initialization and errors
  useEffect(() => {
    if (connectionError) {
      addLogMessage(`✗ System error: ${connectionError}`)
    }
  }, [connectionError])



  // Handle incoming messages from Python backend
  useEffect(() => {
    if (!lastControlMessage) {
      return
    }

    switch (lastControlMessage.type) {
      case 'system_state':
        if (lastControlMessage.state === 'ready') {
          addLogMessage('✓ System ready - all startup checks passed')
        }
        break

      case 'system_status':
        setIsExperimentRunning(Boolean(lastControlMessage.experiment_running))
        break

      case 'experiment_progress':
        setCurrentProgress(lastControlMessage.progress ?? 0)
        break

      case 'log_message':
        if (lastControlMessage.message) {
          addLogMessage(lastControlMessage.message)
        }
        break

      case 'session_started':
        setCurrentSession(lastControlMessage.session_name ?? null)
        if (lastControlMessage.session_name) {
          addLogMessage(`Session started: ${lastControlMessage.session_name}`)
        }
        break

      case 'session_stopped':
        setCurrentSession(null)
        addLogMessage('Session stopped')
        break
    }
  }, [lastControlMessage])

  // Backend automatically manages health checking and sends updates

  const addLogMessage = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogMessages(prev => [...prev.slice(-49), `[${timestamp}] ${message}`])
  }


  const handleStopExperiment = async () => {
    try {
      await sendCommand({
        type: 'stop_experiment'
      })
      setIsExperimentRunning(false)
      setCurrentProgress(0)
      addLogMessage('Experiment stopped')
    } catch (error) {
      componentLogger.error('Failed to stop experiment:', error)
      addLogMessage('ERROR: Failed to stop experiment')
    }
  }

  // Main application - always render the full layout
  return (
    <div className="h-screen flex flex-col bg-sci-secondary-900 text-sci-secondary-100">
      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Control Panel */}
        <div className="border-r border-sci-secondary-700 bg-sci-secondary-800">
          <ControlPanel
            isConnected={isReady}
            isExperimentRunning={isExperimentRunning}
            onStopExperiment={handleStopExperiment}
            onCollapseChange={setIsControlPanelCollapsed}
            isReady={isReady}
            parameterState={parameterState}
            sendCommand={sendCommand}
          />
        </div>

        {/* Main Viewport */}
        <div className="flex-1 flex flex-col">
          <MainViewport
            sendCommand={sendCommand}
            parameterState={parameterState}
            systemStateStr={systemState}
            displayText={displayText}
            isReady={isReady}
            isError={isError}
            errorMessage={errorMessage}
            connectionError={connectionError}
            healthSnapshot={healthSnapshot}
            isExperimentRunning={isExperimentRunning}
            currentProgress={currentProgress}
          />
        </div>
      </div>

      {/* Console at Bottom */}
      <Console
        logMessages={logMessages}
      />
    </div>
  )
}

export default App