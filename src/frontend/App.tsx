import { useState, useEffect } from 'react'
import ControlPanel from './components/ControlPanel'
import MainViewport from './components/MainViewport'
import Console from './components/Console'
import { useISISystem } from './hooks/useISISystem'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  systemStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
    stimulus: 'online' | 'offline' | 'error'
    parameters: 'online' | 'offline' | 'error'
  }
}

function App() {
  const [systemState, setSystemState] = useState<SystemState>({
    isConnected: false,
    isExperimentRunning: false,
    currentProgress: 0,
    systemStatus: {
      camera: 'offline',
      display: 'offline',
      stimulus: 'offline',
      parameters: 'offline'
    }
  })

  const [, setCurrentSession] = useState<string | null>(null)
  const [logMessages, setLogMessages] = useState<string[]>([])
  const [, setIsControlPanelCollapsed] = useState(false)
  const [startupProgress, setStartupProgress] = useState<{
    phase: string
    message: string
    error?: boolean
  }>({
    phase: 'initializing',
    message: 'Starting system...'
  })

  // All parameters managed by backend - no frontend state
  // Hardware lists come from backend parameter manager

  const { sendCommand, isReady, lastMessage, connectionError, initState } = useISISystem()

  // Use centralized hardware status management
  // Remove hardware status hook - backend will manage all health checking

  // Handle system initialization and errors
  useEffect(() => {
    if (initState === 'system-ready') {
      setSystemState(prev => ({
        ...prev,
        isConnected: true
      }))
    } else if (connectionError) {
      setSystemState(prev => ({
        ...prev,
        isConnected: false
      }))
      addLogMessage(`✗ System error: ${connectionError}`)
    }
  }, [initState, connectionError])



  // Handle incoming messages from Python backend
  useEffect(() => {
    if (lastMessage) {

      // Handle different message types
      switch (lastMessage.type) {
        case 'system_status':
          setSystemState(prev => ({
            ...prev,
            isExperimentRunning: lastMessage.experiment_running
          }))
          break

        case 'experiment_progress':
          setSystemState(prev => ({
            ...prev,
            currentProgress: lastMessage.progress
          }))
          break

        case 'system_health':
        case 'system_health_detailed':
          if (lastMessage.hardware_status) {
            setSystemState(prev => ({
              ...prev,
              systemStatus: lastMessage.hardware_status
            }))
          }
          break


        case 'startup_status':
          // Update startup progress from coordinated startup sequence
          setStartupProgress({
            phase: lastMessage.phase,
            message: lastMessage.message,
            error: lastMessage.error
          })
          break

        case 'log_message':
          addLogMessage(lastMessage.message)
          break

        case 'session_started':
          setCurrentSession(lastMessage.session_name)
          addLogMessage(`Session started: ${lastMessage.session_name}`)
          break

        case 'session_stopped':
          setCurrentSession(null)
          addLogMessage('Session stopped')
          break
      }
    }
  }, [lastMessage])

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
      setSystemState(prev => ({
        ...prev,
        isExperimentRunning: false,
        currentProgress: 0
      }))
      addLogMessage('Experiment stopped')
    } catch (error) {
      console.error('Failed to stop experiment:', error)
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
            isConnected={systemState.isConnected}
            isExperimentRunning={systemState.isExperimentRunning}
            onStopExperiment={handleStopExperiment}
            sendCommand={sendCommand}
            onCollapseChange={setIsControlPanelCollapsed}
            isReady={isReady}
            lastMessage={lastMessage}
            systemStatus={systemState.systemStatus}
          />
        </div>

        {/* Main Viewport */}
        <div className="flex-1 flex flex-col">
          <MainViewport
            systemState={systemState}
            sendCommand={sendCommand}
            lastMessage={lastMessage}
            initState={initState}
            connectionError={connectionError}
            startupProgress={startupProgress}
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