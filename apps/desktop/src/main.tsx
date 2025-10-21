import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { SystemProvider } from './context/SystemContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import StimulusPresentationViewport from './components/viewports/StimulusPresentationViewport'

// Remove loading spinner once React app is ready
const loadingElement = document.querySelector('.loading')
if (loadingElement) {
  loadingElement.remove()
}

// Check if this is the presentation window (loaded with #/presentation hash)
const isPresentation = window.location.hash === '#/presentation'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <SystemProvider>
      {isPresentation ? (
        <StimulusPresentationViewport />
      ) : (
        <App />
      )}
    </SystemProvider>
  </ErrorBoundary>
)