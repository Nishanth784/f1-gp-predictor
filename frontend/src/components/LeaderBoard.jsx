import { useState, useEffect } from 'react'
import { getTeamColour } from './TeamColours'

const BADGES = { 0: 'P1', 1: 'P2', 2: 'P3' }
const BADGE_COLOURS = {
  P1: { bg: '#FFD700', text: '#000' },
  P2: { bg: '#C0C0C0', text: '#000' },
  P3: { bg: '#CD7F32', text: '#000' },
}

function ProbBar({ value, max, colour, animate }) {
  const [width, setWidth] = useState(0)
  const pct = max > 0 ? (value / max) * 100 : 0

  useEffect(() => {
    const t = setTimeout(() => setWidth(pct), 80)
    return () => clearTimeout(t)
  }, [pct])

  return (
    <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
      <div style={{
        height: '100%', width: `${animate ? width : pct}%`,
        background: colour, borderRadius: 3,
        transition: animate ? 'width 600ms cubic-bezier(0.25,0.46,0.45,0.94)' : 'none',
        boxShadow: `0 0 8px ${colour}55`,
      }} />
    </div>
  )
}

export default function LeaderBoard({ drivers = [], loading = false }) {
  const [animated, setAnimated] = useState(false)

  useEffect(() => {
    if (drivers.length > 0) {
      setAnimated(false)
      const t = setTimeout(() => setAnimated(true), 50)
      return () => clearTimeout(t)
    }
  }, [drivers])

  const maxProb = drivers.length > 0
    ? Math.max(...drivers.map(d => d.likely_probability ?? d.probability ?? 0))
    : 1

  if (loading) {
    return (
      <div className="space-y-2 p-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} style={{ height: 36, background: 'rgba(255,255,255,0.04)', borderRadius: 4,
            animation: 'pulse 1.5s ease-in-out infinite', animationDelay: `${i * 0.08}s` }} />
        ))}
      </div>
    )
  }

  if (drivers.length === 0) {
    return (
      <div className="flex items-center justify-center h-40">
        <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>AWAITING DATA</span>
      </div>
    )
  }

  return (
    <div style={{ overflowY: 'auto', maxHeight: '100%' }}>
      {drivers.map((d, i) => {
        const prob   = d.likely_probability ?? d.probability ?? 0
        const best   = d.scenarios?.best_case ?? prob
        const worst  = d.scenarios?.worst_case ?? prob
        const colour = getTeamColour(d.team || d.Team || '')
        const badge  = BADGES[i]
        const code   = (d.driver || d.Driver || '').slice(0, 3).toUpperCase()

        return (
          <div
            key={d.driver || d.Driver || i}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              background: i < 3 ? 'rgba(255,255,255,0.02)' : 'transparent',
            }}
          >
            {/* Position / badge */}
            {badge ? (
              <div style={{
                width: 24, height: 20, borderRadius: 3, flexShrink: 0,
                background: BADGE_COLOURS[badge].bg, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700,
                  color: BADGE_COLOURS[badge].text }}>{badge}</span>
              </div>
            ) : (
              <span style={{ width: 24, textAlign: 'center', fontFamily: 'monospace',
                fontSize: 9, color: '#3d4f66', flexShrink: 0 }}>
                P{i + 1}
              </span>
            )}

            {/* Team colour dot */}
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: colour,
              flexShrink: 0, boxShadow: `0 0 6px ${colour}88` }} />

            {/* Driver code */}
            <span style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
              color: '#fff', width: 30, flexShrink: 0 }}>
              {code}
            </span>

            {/* Probability bar */}
            <ProbBar value={prob} max={maxProb} colour={colour} animate={animated} />

            {/* Percentage */}
            <span style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
              color: colour, width: 38, textAlign: 'right', flexShrink: 0 }}>
              {(prob * 100).toFixed(1)}%
            </span>

            {/* Scenario range */}
            <span style={{ fontFamily: 'monospace', fontSize: 8,
              color: '#3d4f66', width: 52, textAlign: 'right', flexShrink: 0 }}>
              {(worst * 100).toFixed(0)}-{(best * 100).toFixed(0)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
