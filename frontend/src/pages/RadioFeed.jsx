import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Radio, Cloud, Wind, Thermometer, Loader } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'
import { parseRouteParams } from '../utils/sanitizeParams'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

const FLAG_META = {
  RED:       { colour: '#E8002D', bg: 'rgba(232,0,45,0.12)',   label: 'RED FLAG' },
  YELLOW:    { colour: '#FFD700', bg: 'rgba(255,215,0,0.10)',   label: 'YELLOW' },
  GREEN:     { colour: '#00ff88', bg: 'rgba(0,255,136,0.08)',   label: 'GREEN' },
  CHEQUERED: { colour: '#ffffff', bg: 'rgba(255,255,255,0.08)', label: 'CHEQUERED' },
  BLUE:      { colour: '#0067ff', bg: 'rgba(0,103,255,0.10)',   label: 'BLUE' },
  CLEAR:     { colour: '#00ff88', bg: 'rgba(0,255,136,0.06)',   label: 'CLEAR' },
}

const CAT_META = {
  SafetyCar:         { colour: '#FFD700', label: 'SAFETY CAR',     icon: '🚗' },
  VirtualSafetyCar:  { colour: '#FFD700', label: 'VIRTUAL SC',     icon: '🟡' },
  Flag:              { colour: '#fff',    label: 'FLAG',            icon: '🏁' },
  Drs:               { colour: '#00ff88', label: 'DRS',             icon: '▲'  },
  Incident:          { colour: '#FF8000', label: 'INCIDENT',        icon: '⚠'  },
  LapTimeDeleted:    { colour: '#E8002D', label: 'LAP DELETED',     icon: '✕'  },
  PenaltyTime:       { colour: '#FF8000', label: 'PENALTY',         icon: '⏱'  },
  TrackSurveillance: { colour: '#FF8000', label: 'TRACK SURVEY',    icon: '👁' },
  Other:             { colour: '#3d4f66', label: 'MESSAGE',         icon: '📻' },
}

function WeatherStrip({ weather }) {
  if (!weather?.length) return null
  const latest = weather[weather.length - 1]
  return (
    <div style={{ display: 'flex', gap: 12, padding: '6px 14px',
      borderBottom: '1px solid #1e2535', background: '#0a0d14',
      flexShrink: 0, alignItems: 'center' }}>
      <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
        letterSpacing: '0.1em' }}>WEATHER</span>
      <div className="flex items-center gap-1">
        <Thermometer size={9} style={{ color: '#FF8000' }} />
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#FF8000' }}>
          AIR {latest.air_temp}°C
        </span>
      </div>
      <div className="flex items-center gap-1">
        <Thermometer size={9} style={{ color: '#E8002D' }} />
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#E8002D' }}>
          TRK {latest.track_temp}°C
        </span>
      </div>
      <div className="flex items-center gap-1">
        <Wind size={9} style={{ color: '#64C4FF' }} />
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#64C4FF' }}>
          {latest.wind_speed}m/s
        </span>
      </div>
      <div className="flex items-center gap-1">
        <Cloud size={9} style={{ color: latest.rainfall ? '#0067ff' : '#3d4f66' }} />
        <span style={{ fontFamily: 'monospace', fontSize: 9,
          color: latest.rainfall ? '#0067ff' : '#3d4f66' }}>
          {latest.humidity}% {latest.rainfall ? 'RAIN' : 'DRY'}
        </span>
      </div>
    </div>
  )
}

function MessageCard({ msg, index }) {
  const cat     = msg.category || 'Other'
  const meta    = CAT_META[cat] || CAT_META.Other
  const isFlag  = cat === 'Flag'
  const flagM   = isFlag ? (FLAG_META[msg.flag] || { colour: meta.colour, bg: 'rgba(255,255,255,0.06)', label: msg.flag }) : null
  const colour  = isFlag ? flagM.colour : meta.colour
  const bg      = isFlag ? flagM.bg     : `${meta.colour}0d`
  const label   = isFlag ? flagM.label  : meta.label

  const isSC    = cat === 'SafetyCar' || cat === 'VirtualSafetyCar'
  const isSerious = cat === 'Incident' || cat === 'LapTimeDeleted' || cat === 'PenaltyTime' || (isFlag && msg.flag === 'RED')

  return (
    <div style={{ display: 'flex', gap: 10, padding: '10px 14px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      background: index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
      borderLeft: `3px solid ${colour}`,
      animation: index === 0 ? 'fadeUp 0.3s ease-out' : 'none' }}>

      {/* Icon */}
      <div style={{ fontSize: 16, flexShrink: 0, minWidth: 20, textAlign: 'center',
        lineHeight: 1.2 }}>{meta.icon}</div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="flex items-center gap-6 mb-1" style={{ flexWrap: 'wrap' }}>
          {/* Category badge */}
          <span style={{ fontFamily: 'monospace', fontSize: 8, fontWeight: 700,
            color: colour, background: bg, padding: '2px 6px', borderRadius: 2 }}>
            {label}
          </span>
          {/* Lap */}
          {msg.lap && (
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>
              LAP {msg.lap}
            </span>
          )}
          {/* Time */}
          {msg.time_s != null && (
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>
              T+{Math.floor(msg.time_s / 60)}:{String(Math.floor(msg.time_s % 60)).padStart(2, '0')}
            </span>
          )}
          {/* Driver number if present */}
          {msg.driver && msg.driver !== '0' && (
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: colour }}>
              #{msg.driver}
            </span>
          )}
        </div>

        {/* Message text */}
        <div style={{ fontFamily: 'monospace', fontSize: 10,
          color: isSerious ? colour : '#8899aa', lineHeight: 1.5 }}>
          {msg.message || '—'}
        </div>
      </div>
    </div>
  )
}

function StatBar({ label, value, max, colour }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="flex justify-between mb-1">
        <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>{label}</span>
        <span style={{ fontFamily: 'monospace', fontSize: 8, fontWeight: 700, color: colour }}>{value}</span>
      </div>
      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
        <div style={{ width: `${Math.min(100, (value / max) * 100)}%`, height: '100%',
          background: colour, borderRadius: 2 }} />
      </div>
    </div>
  )
}

export default function RadioFeed() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [loadMsg, setLoadMsg]   = useState('')
  const [filter, setFilter]     = useState('ALL')
  const [sessionType, setSessionType] = useState('R')
  const feedRef = useRef(null)

  const loadData = () => {
    if (!year || !gpDecoded) return
    setLoading(true)
    setLoadMsg('Loading race control messages...')
    fetch(`${API_BASE}/race-control/${year}/${encodeURIComponent(gpDecoded)}?session_type=${sessionType}`)
      .then(r => r.json())
      .then(d => {
        if (d.detail) throw new Error(d.detail)
        setData(d)
        setLoading(false)
        setLoadMsg('')
      })
      .catch(e => { setLoadMsg(`Error: ${e.message}`); setLoading(false) })
  }

  const allMessages = data?.race_control || []

  const categories = ['ALL', ...new Set(allMessages.map(m => m.category || 'Other'))]

  const filtered = filter === 'ALL'
    ? [...allMessages].reverse()
    : [...allMessages].filter(m => (m.category || 'Other') === filter).reverse()

  // Count by category
  const catCounts = {}
  for (const m of allMessages) {
    const c = m.category || 'Other'
    catCounts[c] = (catCounts[c] || 0) + 1
  }
  const scCount  = (catCounts['SafetyCar'] || 0) + (catCounts['VirtualSafetyCar'] || 0)
  const incCount = catCounts['Incident'] || 0
  const flagCount = catCounts['Flag'] || 0

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      {/* Weather strip */}
      {data?.weather && <WeatherStrip weather={data.weather} />}

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px',
        borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0, flexWrap: 'wrap' }}>
        <Radio size={11} style={{ color: '#3d4f66' }} />
        <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66',
          letterSpacing: '0.12em' }}>RACE CONTROL FEED</span>

        {['R','Q','FP1','FP2','FP3'].map(st => (
          <button key={st} onClick={() => setSessionType(st)}
            style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
              fontFamily: 'monospace', fontSize: 8, fontWeight: 700,
              border: `1px solid ${sessionType === st ? '#E8002D' : '#1e2535'}`,
              background: sessionType === st ? 'rgba(232,0,45,0.12)' : 'transparent',
              color: sessionType === st ? '#E8002D' : '#3d4f66' }}>
            {st}
          </button>
        ))}

        <button onClick={loadData} disabled={loading}
          style={{ padding: '3px 12px', borderRadius: 4, cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'monospace', fontSize: 9, fontWeight: 700,
            background: '#E8002D', color: '#fff', border: 'none', opacity: loading ? 0.6 : 1 }}>
          {loading ? 'LOADING...' : 'LOAD'}
        </button>

        {loading && <Loader size={11} style={{ color: '#E8002D', animation: 'spin 1s linear infinite' }} />}
        {loadMsg && <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#E8002D' }}>{loadMsg}</span>}

        {/* Category filters */}
        {data && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {categories.map(c => {
              const meta = CAT_META[c] || { colour: '#3d4f66' }
              return (
                <button key={c} onClick={() => setFilter(c)}
                  style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                    fontFamily: 'monospace', fontSize: 7,
                    border: `1px solid ${filter === c ? meta.colour : '#1e2535'}`,
                    background: filter === c ? `${meta.colour}18` : 'transparent',
                    color: filter === c ? meta.colour : '#3d4f66' }}>
                  {c === 'ALL' ? `ALL (${allMessages.length})` : `${c} (${catCounts[c] || 0})`}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Main grid */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 200px',
        gap: 8, padding: 10, minHeight: 0, overflow: 'hidden' }}>

        {/* Feed */}
        <div ref={feedRef} style={{ background: '#0d1018', border: '1px solid #1e2535',
          borderRadius: 6, overflowY: 'auto' }}>
          {!data && !loading && (
            <div className="flex items-center justify-center" style={{ height: 200 }}>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#3d4f66' }}>
                SELECT SESSION TYPE AND CLICK LOAD
              </span>
            </div>
          )}
          {filtered.map((msg, i) => <MessageCard key={i} msg={msg} index={i} />)}
          {data && filtered.length === 0 && (
            <div className="flex items-center justify-center" style={{ height: 100 }}>
              <span style={{ fontFamily: 'monospace', fontSize: 10, color: '#3d4f66' }}>
                NO MESSAGES IN THIS CATEGORY
              </span>
            </div>
          )}
        </div>

        {/* Stats sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Session summary */}
          <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
            padding: '12px 14px' }}>
            <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
              letterSpacing: '0.12em', marginBottom: 10 }}>SESSION SUMMARY</div>
            <StatBar label="Total Messages" value={allMessages.length} max={Math.max(50, allMessages.length)} colour="#8899aa" />
            <StatBar label="Safety Cars"    value={scCount}            max={Math.max(5, scCount)}            colour="#FFD700" />
            <StatBar label="Incidents"      value={incCount}           max={Math.max(10, incCount)}          colour="#FF8000" />
            <StatBar label="Flag Events"    value={flagCount}          max={Math.max(10, flagCount)}         colour="#fff" />
            {data?.total_laps > 0 && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #1e2535' }}>
                <div style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>TOTAL LAPS</div>
                <div style={{ fontFamily: 'monospace', fontSize: 20, fontWeight: 700, color: '#E8002D' }}>
                  {data.total_laps}
                </div>
              </div>
            )}
          </div>

          {/* Flag breakdown */}
          {data && (
            <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
              padding: '12px 14px' }}>
              <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
                letterSpacing: '0.12em', marginBottom: 10 }}>FLAG BREAKDOWN</div>
              {Object.entries(FLAG_META).map(([flag, m]) => {
                const count = allMessages.filter(msg =>
                  msg.category === 'Flag' && msg.flag === flag).length
                if (!count) return null
                return (
                  <div key={flag} className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div style={{ width: 10, height: 10, background: m.colour, borderRadius: 1 }} />
                      <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>{m.label}</span>
                    </div>
                    <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: m.colour }}>
                      x{count}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Latest weather */}
          {data?.weather?.length > 0 && (
            <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
              padding: '12px 14px', flex: 1 }}>
              <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
                letterSpacing: '0.12em', marginBottom: 10 }}>WEATHER TREND</div>
              {data.weather.slice(-8).map((w, i) => (
                <div key={i} className="flex items-center justify-between" style={{ marginBottom: 4 }}>
                  <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66' }}>
                    {w.time_s != null ? `T+${Math.floor(w.time_s/60)}m` : `P${i+1}`}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#FF8000' }}>
                    {w.air_temp}°
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#E8002D' }}>
                    {w.track_temp}°
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: 7,
                    color: w.rainfall ? '#0067ff' : '#3d4f66' }}>
                    {w.rainfall ? 'RAIN' : 'DRY'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
