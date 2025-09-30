import React from 'react'
import ReactDOM from 'react-dom/client'
import StimulusPresentationViewport from './components/viewports/StimulusPresentationViewport'
import './index.css' // Use the same global styles

// Render only the StimulusPresentationViewport in fullscreen on second display
ReactDOM.createRoot(document.getElementById('presentation-root')!).render(
  <React.StrictMode>
    <StimulusPresentationViewport />
  </React.StrictMode>,
)