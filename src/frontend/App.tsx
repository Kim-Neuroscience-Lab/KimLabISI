import React, { useState, useEffect } from 'react'
import ControlPanel from './components/ControlPanel'
import MainViewport from './components/MainViewport'
import Console from './components/Console'
import { useISISystem } from './hooks/useISISystem'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  hardwareStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
  }
}

function App() {
  const [systemState, setSystemState] = useState<SystemState>({
    isConnected: false,
    isExperimentRunning: false,
    currentProgress: 0,
    hardwareStatus: {
      camera: 'offline',
      display: 'offline'
    }
  })

  const [currentSession, setCurrentSession] = useState<string | null>(null)
  const [logMessages, setLogMessages] = useState<string[]>([])
  const [isControlPanelCollapsed, setIsControlPanelCollapsed] = useState(false)

  const { sendCommand, isReady, lastMessage, connectionError } = useISISystem()

  // Handle system initialization and errors
  useEffect(() => {
    if (isReady) {
      setSystemState(prev => ({
        ...prev,
        isConnected: true
      }))
      addLogMessage('System connected and ready')
    } else if (connectionError) {
      setSystemState(prev => ({
        ...prev,
        isConnected: false,
        hardwareStatus: {
          camera: 'error',
          display: 'error'
        }
      }))
      addLogMessage(`System error: ${connectionError}`)
    }
  }, [isReady, connectionError])

  // Handle incoming messages from Python backend
  useEffect(() => {
    if (lastMessage) {

      // Handle different message types
      switch (lastMessage.type) {
        case 'system_status':
          setSystemState(prev => ({
            ...prev,
            hardwareStatus: lastMessage.hardware_status,
            isExperimentRunning: lastMessage.experiment_running
          }))
          break

        case 'experiment_progress':
          setSystemState(prev => ({
            ...prev,
            currentProgress: lastMessage.progress
          }))
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

  // Periodic status monitoring
  useEffect(() => {
    if (!isReady) return

    const statusInterval = setInterval(async () => {
      try {
        await window.electronAPI.getSystemStatus()
      } catch (error) {
        console.error('Status check failed:', error)
      }
    }, 30000) // Check every 30 seconds

    // Initial status check
    window.electronAPI.getSystemStatus().catch(console.error)

    return () => clearInterval(statusInterval)
  }, [isReady])

  const addLogMessage = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogMessages(prev => [...prev.slice(-49), `[${timestamp}] ${message}`])
  }

  const handleEmergencyStop = async () => {
    try {
      await window.electronAPI.emergencyStop()
      addLogMessage('EMERGENCY STOP activated')
      setSystemState(prev => ({
        ...prev,
        isExperimentRunning: false,
        currentProgress: 0
      }))
    } catch (error) {
      console.error('Emergency stop failed:', error)
      addLogMessage('ERROR: Emergency stop failed')
    }
  }

  const handleStartExperiment = async (params: any) => {
    try {
      await sendCommand({
        type: 'start_experiment',
        parameters: params
      })
      setSystemState(prev => ({
        ...prev,
        isExperimentRunning: true,
        currentProgress: 0
      }))
      addLogMessage('Experiment started')
    } catch (error) {
      console.error('Failed to start experiment:', error)
      addLogMessage('ERROR: Failed to start experiment')
    }
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

  return (
    <div className="h-screen flex flex-col bg-sci-secondary-900 text-sci-secondary-100">
      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Control Panel */}
        <div className="border-r border-sci-secondary-700 bg-sci-secondary-800">
          <ControlPanel
            isConnected={systemState.isConnected}
            isExperimentRunning={systemState.isExperimentRunning}
            hardwareStatus={systemState.hardwareStatus}
            onStopExperiment={handleStopExperiment}
            sendCommand={sendCommand}
            onCollapseChange={setIsControlPanelCollapsed}
            isReady={isReady}
          />
        </div>

        {/* Main Viewport */}
        <div className="flex-1 flex flex-col">
          <MainViewport
            systemState={systemState}
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