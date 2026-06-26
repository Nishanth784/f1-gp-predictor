/**
 * ErrorBoundary.jsx
 *
 * Global React error boundary. Catches unhandled render errors in the subtree
 * and shows a styled fallback instead of a blank / crashed screen.
 *
 * Usage (in main.jsx):
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 *
 * Per-page usage (isolate one route from crashing the whole app):
 *   <ErrorBoundary label="Timing Tower">
 *     <TimingTower />
 *   </ErrorBoundary>
 */

import { Component } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

const BOX = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#0a0e17',
  padding: '2rem',
}

const CARD = {
  maxWidth: 480,
  width: '100%',
  background: '#131926',
  border: '1px solid rgba(232,0,45,0.35)',
  borderRadius: 12,
  padding: '2.5rem 2rem',
  textAlign: 'center',
}

const ICON_WRAP = {
  display: 'flex',
  justifyContent: 'center',
  marginBottom: '1.25rem',
}

const TITLE = {
  fontFamily: "'Barlow Condensed', sans-serif",
  fontSize: '1.5rem',
  fontWeight: 700,
  color: '#e8002d',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: '0.5rem',
}

const MSG = {
  color: '#8899aa',
  fontSize: '0.9rem',
  lineHeight: 1.6,
  marginBottom: '1.5rem',
}

const DETAIL = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: '0.7rem',
  color: '#556677',
  background: '#0a0e17',
  border: '1px solid #1e2a3a',
  borderRadius: 6,
  padding: '0.75rem',
  textAlign: 'left',
  overflowX: 'auto',
  marginBottom: '1.5rem',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
}

const BTN = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.4rem',
  padding: '0.6rem 1.25rem',
  background: '#e8002d',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  fontFamily: "'Barlow Condensed', sans-serif",
  fontWeight: 700,
  fontSize: '0.95rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  cursor: 'pointer',
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
    this._handleReset = this._handleReset.bind(this)
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    // In production you could ship this to Sentry / LogRocket here
    console.error('[ErrorBoundary] Caught:', error, info?.componentStack)
  }

  _handleReset() {
    this.setState({ hasError: false, error: null, info: null })
    // Navigate to root so a broken URL param doesn't immediately re-crash
    if (typeof window !== 'undefined') {
      window.location.href = '/'
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const { label = 'this page' } = this.props
    const errMsg = this.state.error?.message || 'Unknown error'
    const isDev = import.meta.env.DEV

    return (
      <div style={BOX}>
        <div style={CARD}>
          <div style={ICON_WRAP}>
            <AlertTriangle size={48} color="#e8002d" strokeWidth={1.5} />
          </div>
          <div style={TITLE}>Something went wrong</div>
          <p style={MSG}>
            {label.charAt(0).toUpperCase() + label.slice(1)} crashed unexpectedly.
            Try going back to the home screen — your model data is fine.
          </p>

          {isDev && (
            <pre style={DETAIL}>{errMsg}</pre>
          )}

          <button style={BTN} onClick={this._handleReset}>
            <RotateCcw size={14} />
            Return to home
          </button>
        </div>
      </div>
    )
  }
}
