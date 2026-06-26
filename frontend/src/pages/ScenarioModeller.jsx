import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Sliders, AlertTriangle, RefreshCw } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'
import { parseRouteParams } from '../utils/sanitizeParams'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function Slider({ label, value, onChange, min = 0, max = 1, step = 0.01, format = v => `${Math.round(v * 100)}%`, colour = '#E8002D' }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>{label}</span>
        <span className="font-mono font-bold text-xs" style={{ color: colour }}>{format(value)}</span>
      </div>
      <div style={{ position: 'relative', height: 6 }}>
        <div style={{ position: 'absolute', inset: '2px 0', background: 'rgba(255,255,255,0.06)', borderRadius: 3 }} />
        <div style={{ position: 'absolute', left: 0, top: 2, bottom: 2,
          width: `${((value - min) / (max - min)) * 100}%`,
          background: colour, borderRadius: 3,
          boxShadow: `0 0 8px ${colour}55`, transition: 'width 0.05s' }} />
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
          style={{ position: 'absolute', inset: 0, width: '100%', opacity: 0, cursor: 'pointer', height: '100%' }}
        />
      </div>
    </div>
  )
}

function ScenarioBar({ label, value, max = 0.5, colour, animated }) {
  const [width, setWidth] = useState(0)
  const pct = Math.min(100, (value / max) * 100)
  useEffect(() => {
    if (animated) { const t = setTimeout(() => setWidth(pct), 80); return () => clearTimeout(t) }
    else setWidth(pct)
  }, [pct, animated])
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 28, fontFamily: 'monospace', fontSize: 9, color: '#3d4f66', flexShrink: 0 }}>{label}</div>
      <div style={{ flex: 1, height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${width}%`, height: '100%', background: colour, borderRadius: 4,
          boxShadow: `0 0 8px ${colour}55`,
          transition: animated ? 'width 400ms cubic-bezier(0.25,0.46,0.45,0.94)' : 'width 0.15s ease' }} />
      </div>
      <div style={{ width: 40, fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
        color: colour, textAlign: 'right', flexShrink: 0 }}>
        {(value * 100).toFixed(1)}%
      </div>
    </div>
  )
}

// Recalculate probabilities client-side based on slider inputs
function recalcPredictions(basePredictions, scProb, weatherVariance, gridSpread) {
  if (!basePredictions?.length) return []
  const chaosBoost = (scProb * 0.4 + weatherVariance * 0.35 + gridSpread * 0.25)
  return basePredictions.map((d, i) => {
    const base = d.likely_probability ?? d.probability ?? 0
    // Front-runners hurt by chaos, midfielders helped
    const positionFactor = i < 3 ? (1 - chaosBoost * 0.3) : (1 + chaosBoost * 0.15)
    const adjusted = Math.max(0.001, Math.min(0.99, base * positionFactor))
    const variance = adjusted * (weatherVariance * 0.4 + gridSpread * 0.3)
    return {
      ...d,
      likely_probability: adjusted,
      scenarios: {
        best_case:  Math.min(0.99, adjusted + variance * scProb),
        likely:     adjusted,
        worst_case: Math.max(0.001, adjusted - variance),
      },
    }
  })
}

function chaosFromSliders(sc, weather, grid) {
  return Math.min(1, sc * 0.4 + weather * 0.35 + grid * 0.25)
}

export default function ScenarioModeller() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [baseData, setBaseData]   = useState(null)
  const [loading, setLoading]     = useState(false)

  // Slider values
  const [scProb,  setScProb]      = useState(0.3)
  const [weather, setWeather]     = useState(0.2)
  const [grid,    setGrid]        = useState(0.3)
  const [animated, setAnimated]   = useState(false)

  useEffect(() => {
    if (!year || !gpDecoded) return
    setLoading(true)
    fetch(`${API_BASE}/winner-probabilities?year=${year}&gp=${encodeURIComponent(gpDecoded)}`)
      .then(r => r.json())
      .then(d => {
        setBaseData(d)
        setLoading(false)
        // Seed sliders from actual chaos/sc_rate
        if (d.chaos_index != null) setWeather(d.chaos_index * 0.5)
        if (d.sc_rate != null)     setScProb(d.sc_rate)
        setAnimated(true)
      })
      .catch(() => setLoading(false))
  }, [year, gpDecoded])

  // Reset to original
  const reset = useCallback(() => {
    if (!baseData) return
    setScProb(baseData.sc_rate ?? 0.3)
    setWeather((baseData.chaos_index ?? 0.4) * 0.5)
    setGrid(0.3)
    setAnimated(true)
  }, [baseData])

  const adjustedPredictions = recalcPredictions(
    baseData?.predictions || [], scProb, weather, grid
  ).sort((a, b) => (b.likely_probability ?? 0) - (a.likely_probability ?? 0))

  const chaos = chaosFromSliders(scProb, weather, grid)
  const chaosHigh = chaos >= 0.7
  const chaosColour = chaos >= 0.7 ? '#E8002D' : chaos >= 0.4 ? '#FFD700' : '#00ff88'
  const baseChaos = baseData?.chaos_index ?? null

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      {/* Chaos alert banner */}
      {chaosHigh && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px',
          background: 'rgba(232,0,45,0.12)', borderBottom: '1px solid rgba(232,0,45,0.3)',
          animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }}>
          <AlertTriangle size={14} style={{ color: '#E8002D' }} />
          <span className="font-mono text-xs font-bold" style={{ color: '#E8002D' }}>
            HIGH CHAOS DETECTED — PREDICTIONS HIGHLY VOLATILE
          </span>
          <span className="font-mono text-xs" style={{ color: 'rgba(232,0,45,0.7)', marginLeft: 4 }}>
            Chaos Index: {chaos.toFixed(2)}
          </span>
        </div>
      )}

      <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
        gridTemplateColumns: '280px 1fr', minHeight: 0 }}>

        {/* LEFT: Sliders */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Control panel */}
          <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
            padding: '12px 14px' }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sliders size={11} style={{ color: '#3d4f66' }} />
                <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>
                  SCENARIO CONTROLS
                </span>
              </div>
              <button onClick={reset}
                style={{ background: 'transparent', border: '1px solid #1e2535', borderRadius: 4,
                  padding: '3px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                <RefreshCw size={9} style={{ color: '#3d4f66' }} />
                <span className="font-mono" style={{ fontSize: 8, color: '#3d4f66' }}>RESET</span>
              </button>
            </div>

            <Slider label="Safety Car Probability" value={scProb} onChange={setScProb} colour="#FF8000" />
            <Slider label="Weather / Track Variance" value={weather} onChange={setWeather} colour="#64C4FF" />
            <Slider label="Grid Spread / Competitiveness" value={grid} onChange={setGrid} colour="#27F4D2" />
          </div>

          {/* Live chaos meter */}
          <div style={{ background: '#0d1018', border: `1px solid ${chaosHigh ? '#E8002D' : '#1e2535'}`,
            borderRadius: 6, padding: '12px 14px',
            transition: 'border-color 0.3s' }}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>CHAOS INDEX</span>
              <span className="font-mono font-bold" style={{ fontSize: 20, color: chaosColour }}>
                {chaos.toFixed(2)}
              </span>
            </div>
            {/* Segment bar */}
            <div style={{ display: 'flex', gap: 2, marginBottom: 8 }}>
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} style={{ flex: 1, height: 10, borderRadius: 2,
                  background: i < Math.round(chaos * 10) ? chaosColour : 'rgba(255,255,255,0.06)',
                  transition: 'background 0.15s',
                  boxShadow: i < Math.round(chaos * 10) ? `0 0 4px ${chaosColour}66` : 'none' }} />
              ))}
            </div>
            {baseChaos != null && (
              <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>
                Base: {baseChaos.toFixed(2)} →
                <span style={{ color: chaos > baseChaos ? '#E8002D' : '#00ff88', marginLeft: 4 }}>
                  {chaos > baseChaos ? '+' : ''}{((chaos - baseChaos) * 100).toFixed(0)}pp
                </span>
              </div>
            )}
          </div>

          {/* Factor breakdown */}
          <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
            padding: '12px 14px' }}>
            <div className="font-mono text-xs tracking-widest mb-3" style={{ color: '#3d4f66' }}>
              FACTOR WEIGHTS
            </div>
            <ScenarioBar label="SC"  value={scProb * 0.4}  max={0.4} colour="#FF8000" animated={false} />
            <div style={{ marginBottom: 6 }} />
            <ScenarioBar label="WX"  value={weather * 0.35} max={0.35} colour="#64C4FF" animated={false} />
            <div style={{ marginBottom: 6 }} />
            <ScenarioBar label="GRD" value={grid * 0.25}   max={0.25} colour="#27F4D2" animated={false} />
          </div>
        </div>

        {/* RIGHT: Adjusted predictions */}
        <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
          display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '6px 14px', borderBottom: '1px solid #1e2535', background: '#0a0d14',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
            <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>
              ADJUSTED WIN PROBABILITIES
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>
              LIVE SCENARIO — MOVE SLIDERS TO UPDATE
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading ? (
              <div className="flex items-center justify-center h-40">
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>LOADING PREDICTIONS...</span>
              </div>
            ) : adjustedPredictions.length === 0 ? (
              <div className="flex items-center justify-center h-40">
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>SELECT A RACE FIRST</span>
              </div>
            ) : adjustedPredictions.map((d, i) => {
              const colour  = getTeamColour(d.team || d.Team || '')
              const likely  = d.likely_probability ?? 0
              const best    = d.scenarios?.best_case ?? likely
              const worst   = d.scenarios?.worst_case ?? likely
              const code    = (d.driver || d.Driver || '').slice(0, 3).toUpperCase()
              const maxProb = adjustedPredictions[0]?.likely_probability ?? 1

              return (
                <div key={d.driver || d.Driver || i}
                  style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)',
                    background: i < 3 ? 'rgba(255,255,255,0.015)' : 'transparent' }}>
                  <div className="flex items-center gap-8 mb-2">
                    <div style={{ width: 24, fontFamily: 'monospace', fontSize: 10,
                      color: i === 0 ? '#FFD700' : i === 1 ? '#C0C0C0' : i === 2 ? '#CD7F32' : '#3d4f66',
                      fontWeight: 700, flexShrink: 0 }}>
                      P{i+1}
                    </div>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: colour,
                      boxShadow: `0 0 6px ${colour}88`, flexShrink: 0 }} />
                    <span style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
                      color: '#fff', width: 32 }}>{code}</span>
                    <div style={{ flex: 1, height: 8, background: 'rgba(255,255,255,0.06)',
                      borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
                      {/* Best case (faint) */}
                      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
                        width: `${(best / maxProb) * 100}%`,
                        background: `${colour}22`, transition: 'width 0.15s ease' }} />
                      {/* Likely */}
                      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
                        width: `${(likely / maxProb) * 100}%`,
                        background: colour, transition: 'width 0.15s ease',
                        boxShadow: `0 0 8px ${colour}55` }} />
                    </div>
                    <span style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
                      color: colour, width: 44, textAlign: 'right', flexShrink: 0 }}>
                      {(likely * 100).toFixed(1)}%
                    </span>
                    <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66',
                      width: 56, textAlign: 'right', flexShrink: 0 }}>
                      {(worst * 100).toFixed(0)}-{(best * 100).toFixed(0)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  )
}
