import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import './styles.css'
import ErrorBoundary from './components/ErrorBoundary'
import RaceControl from './pages/RaceControl'
import TelemetryWall from './pages/TelemetryWall'
import DriverIntel from './pages/DriverIntel'

import TimingTower from './pages/TimingTower'
import RadioFeed from './pages/RadioFeed'
import Results from './pages/Results'
import LivePitWall from './pages/LivePitWall'

// Wrap each page in its own ErrorBoundary so one crashing route
// doesn't take down the whole app. The label surfaces in the fallback UI.
function page(Component, label) {
  return (
    <ErrorBoundary label={label}>
      <Component />
    </ErrorBoundary>
  )
}

const router = createBrowserRouter([
  { path: '/',                        element: page(RaceControl,       'race control') },
  { path: '/race/:year/:gp',          element: page(RaceControl,       'race control') },
  { path: '/telemetry/:year/:gp',     element: page(TelemetryWall,     'telemetry wall') },
  { path: '/intel/:year/:gp',         element: page(DriverIntel,       'driver intel') },
  { path: '/scenario/:year/:gp',      element: <Navigate to="/" replace /> },
  { path: '/timing/:year/:gp',        element: page(TimingTower,       'timing tower') },
  { path: '/radio/:year/:gp',         element: page(RadioFeed,         'RC feed') },
  { path: '/results/:year/:gp',       element: page(Results,           'results') },
  { path: '/live',                    element: page(LivePitWall,       'live pit wall') },
  { path: '*',                        element: <Navigate to="/" replace /> },
])

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary label="the app">
      <RouterProvider router={router} />
    </ErrorBoundary>
  </React.StrictMode>
)
