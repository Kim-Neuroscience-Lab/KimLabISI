import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Remove loading spinner once React app is ready
const loadingElement = document.querySelector('.loading')
if (loadingElement) {
  loadingElement.remove()
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <App />
)