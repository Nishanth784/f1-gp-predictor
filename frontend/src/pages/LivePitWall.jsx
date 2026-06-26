import { useState, useEffect, useRef, useCallback } from 'react'
import { Activity, Wifi, WifiOff, Radio, Cloud, Flag, AlertTriangle, Play, Square, MapPin } from 'lucide-react'

const WS_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8011')
  .replace(/^http/, 'ws')

const COMPOUND_COLOUR = {
  SOFT:    '#E8002D',
  MEDIUM:  '#FFD700',
  HARD:    '#FFFFFF',
  INTER:   '#39B54A',
  WET:     '#0067FF',
  UNKNOWN: '#888888',
}

const TRACK_STATUS_META = {
  AllClear:          { label: 'TRACK CLEAR',       colour: '#00ff88', bg: 'rgba(0,255,136,0.08)' },
  SafetyCar:         { label: 'SAFETY CAR',         colour: '#FFD700', bg: 'rgba(255,215,0,0.12)' },
  VirtualSafetyCar:  { label: 'VIRTUAL SAFETY CAR', colour: '#FF8000', bg: 'rgba(255,128,0,0.12)' },
  RedFlag:           { label: 'RED FLAG',            colour: '#E8002D', bg: 'rgba(232,0,45,0.15)' },
}

const TYRE_ICON = c => {
  const col = COMPOUND_COLOUR[c] || '#888'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 22, borderRadius: '50%',
      border: `2px solid ${col}`, background: c === 'HARD' ? '#111' : `${col}22`,
      fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: col, flexShrink: 0,
    }}>
      {c[0]}
    </span>
  )
}

function WsStatus({ status }) {
  const map = {
    connecting: { icon: <Activity size={10} />, label: 'CONNECTING', colour: '#FF8000' },
    live:       { icon: <Wifi size={10} />,     label: 'LIVE',       colour: '#00ff88' },
    offline:    { icon: <WifiOff size={10} />,  label: 'OFFLINE',    colour: '#E8002D' },
    replay:     { icon: <Activity size={10} />, label: 'HISTORICAL', colour: '#64C4FF' },
  }
  const m = map[status] || map.offline
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4,
      padding: '3px 8px', borderRadius: 3,
      background: `${m.colour}18`, border: `1px solid ${m.colour}44` }}>
      <span style={{ color: m.colour }}>{m.icon}</span>
      <span className="font-mono" style={{ fontSize: 9, color: m.colour, fontWeight: 700 }}>
        {m.label}
      </span>
    </div>
  )
}

function DriverRow({ driver, rank, isFirst }) {
  const col = driver.team_colour || '#888888'
  const gap = isFirst ? 'LEADER' : (driver.gap_to_leader || '—')
  const posCol = rank === 1 ? '#FFD700' : rank === 2 ? '#C0C0C0' : rank === 3 ? '#CD7F32' : '#3d4f66'
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '28px 6px 36px 1fr 70px 70px 46px 50px',
      alignItems: 'center', gap: 6, padding: '7px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      background: isFirst ? 'rgba(255,255,255,0.02)' : 'transparent',
    }}>
      <span className="font-mono font-bold" style={{ fontSize: 13, color: posCol }}>
        P{driver.position < 99 ? driver.position : '—'}
      </span>
      <div style={{ width: 3, height: 28, background: col, borderRadius: 2, opacity: 0.85 }} />
      <span className="font-mono font-bold" style={{ fontSize: 12, color: '#fff', letterSpacing: 1 }}>
        {driver.acronym}
      </span>
      <span className="font-mono" style={{ fontSize: 9, color: col, opacity: 0.8,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {(driver.team || '').toUpperCase()}
      </span>
      <span className="font-mono" style={{ fontSize: 10, textAlign: 'right', fontWeight: isFirst ? 700 : 400,
        color: isFirst ? '#00ff88' : '#8899aa' }}>
        {gap}
      </span>
      <span className="font-mono" style={{ fontSize: 10, color: '#3d4f66', textAlign: 'right' }}>
        {driver.last_lap_fmt || '—'}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'center' }}>
        {TYRE_ICON(driver.compound || 'UNKNOWN')}
        <span className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>{driver.tyre_age || 0}L</span>
      </div>
      {driver.is_pit_out ? (
        <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#FF8000',
          background: 'rgba(255,128,0,0.15)', padding: '2px 4px', borderRadius: 2, textAlign: 'center' }}>
          PIT OUT
        </span>
      ) : (
        <span className="font-mono" style={{ fontSize: 9, color: '#2a3545', textAlign: 'center' }}>
          L{driver.current_lap || '—'}
        </span>
      )}
    </div>
  )
}

function RcMessage({ msg }) {
  const flagColour = {
    GREEN: '#00ff88', YELLOW: '#FFD700', RED: '#E8002D',
    BLUE: '#64C4FF', CHEQUERED: '#fff', CLEAR: '#00ff88',
  }
  const col = flagColour[(msg.flag || '').toUpperCase()] || '#3d4f66'
  return (
    <div style={{ padding: '6px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <div style={{ width: 3, height: '100%', minHeight: 16, background: col,
        borderRadius: 2, flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <div className="font-mono" style={{ fontSize: 9, color: '#3d4f66', marginBottom: 2 }}>
          {msg.lap ? `LAP ${msg.lap} · ` : ''}{msg.category || 'RC'}
        </div>
        <div className="font-mono" style={{ fontSize: 10, color: '#c0cfe0', lineHeight: 1.4 }}>
          {msg.message}
        </div>
      </div>
    </div>
  )
}

function RadioClip({ clip }) {
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef(null)

  const toggle = () => {
    if (!clip.recording_url) return
    if (!audioRef.current) {
      audioRef.current = new Audio(clip.recording_url)
      audioRef.current.onended = () => setPlaying(false)
      audioRef.current.onerror = () => setPlaying(false)
    }
    if (playing) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setPlaying(false)
    } else {
      audioRef.current.play().catch(() => setPlaying(false))
      setPlaying(true)
    }
  }

  useEffect(() => () => { audioRef.current?.pause() }, [])

  const col = clip.team_colour || '#888888'
  const ts  = clip.date
    ? new Date(clip.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <div style={{ padding: '7px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex', gap: 8, alignItems: 'center',
      background: playing ? 'rgba(0,255,136,0.04)' : 'transparent' }}>
      <div style={{ width: 3, height: 32, background: col, borderRadius: 2, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
          <span className="font-mono font-bold" style={{ fontSize: 11, color: '#fff' }}>{clip.acronym}</span>
          <span className="font-mono" style={{ fontSize: 8, color: col, opacity: 0.8,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {(clip.team || '').toUpperCase()}
          </span>
        </div>
        <div className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>{ts}</div>
      </div>
      <button onClick={toggle} style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        border: `1px solid ${playing ? '#00ff88' : '#1e2535'}`,
        background: playing ? 'rgba(0,255,136,0.12)' : '#0d1018',
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: playing ? '#00ff88' : '#3d4f66', transition: 'all 0.15s',
      }}>
        {playing ? <Square size={9} fill="currentColor" /> : <Play size={9} fill="currentColor" />}
      </button>
    </div>
  )
}

function TrackMap({ outline, cars, wsStatus }) {
  const W = 340, H = 300, PAD = 18

  const allPts = [
    ...(outline || []),
    ...(cars   || []).map(c => ({ x: c.x, y: c.y })),
  ]

  if (allPts.length === 0) {
    const msg = wsStatus === 'connecting' ? 'CONNECTING...'
              : wsStatus === 'offline'    ? 'OFFLINE — RETRYING'
              : wsStatus === 'live'       ? 'BUILDING TRACK MAP…'
              :                            'NO ACTIVE SESSION'
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex',
        alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
        <MapPin size={16} style={{ color: '#1e2535' }} />
        <span className="font-mono" style={{ fontSize: 9, color: '#1e2535' }}>{msg}</span>
        {wsStatus === 'live' && (
          <span className="font-mono" style={{ fontSize: 8, color: '#2a3545' }}>
            GPS data arrives after first lap
          </span>
        )}
      </div>
    )
  }

  const xs = allPts.map(p => p.x)
  const ys = allPts.map(p => p.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const rangeX = maxX - minX || 1
  const rangeY = maxY - minY || 1

  const scaleX = (W - 2 * PAD) / rangeX
  const scaleY = (H - 2 * PAD) / rangeY
  const scale  = Math.min(scaleX, scaleY)
  const offX   = (W - rangeX * scale) / 2
  const offY   = (H - rangeY * scale) / 2

  const nx = x =>  offX + (x - minX) * scale
  const ny = y => H - offY - (y - minY) * scale

  const hasOutline = outline && outline.length > 20
  const pts = hasOutline
    ? outline.map(p => `${nx(p.x).toFixed(1)},${ny(p.y).toFixed(1)}`).join(' ')
    : ''

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      {hasOutline && (
        <>
          <polyline points={pts} fill="none" stroke="#0d1520" strokeWidth={10}
            strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={pts} fill="none" stroke="#1a2535" strokeWidth={6}
            strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={pts} fill="none" stroke="#243552" strokeWidth={1.5}
            strokeDasharray="5 8" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
      {!hasOutline && (
        <text x={W / 2} y={H / 2} textAnchor="middle"
          fill="#1e2535" fontFamily="monospace" fontSize={9}>
          BUILDING TRACK MAP…
        </text>
      )}
      {(cars || []).map(car => {
        const cx = nx(car.x), cy = ny(car.y)
        return (
          <g key={car.driver_number}>
            <circle cx={cx} cy={cy} r={7}  fill={car.team_colour} opacity={0.18} />
            <circle cx={cx} cy={cy} r={4}  fill={car.team_colour} />
            <text x={cx} y={cy - 8} textAnchor="middle"
              fill={car.team_colour} fontFamily="monospace" fontSize={6} fontWeight="bold">
              {car.acronym}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function WeatherStrip({ wx }) {
  if (!wx) return null
  return (
    <div style={{ display: 'flex', gap: 16, padding: '5px 12px',
      background: '#0a0d14', borderBottom: '1px solid #1e2535',
      alignItems: 'center', flexShrink: 0 }}>
      <Cloud size={10} style={{ color: '#3d4f66' }} />
      <span className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>
        AIR <span style={{ color: '#8899aa' }}>{wx.air_temp?.toFixed(1)}°C</span>
      </span>
      <span className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>
        TRACK <span style={{ color: '#8899aa' }}>{wx.track_temp?.toFixed(1)}°C</span>
      </span>
      <span className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>
        WIND <span style={{ color: '#8899aa' }}>{wx.wind_speed?.toFixed(1)} m/s</span>
      </span>
      {wx.rainfall && (
        <span className="font-mono" style={{ fontSize: 9, color: '#64C4FF', fontWeight: 700 }}>
          🌧 RAIN
        </span>
      )}
    </div>
  )
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

export default function LivePitWall() {
  const [state, setState]           = useState(null)
  const [wsStatus, setStatus]       = useState('connecting')
  const [rightTab, setRightTab]     = useState('rc')
  const [circuitOutline, setCircuit] = useState([])   // pre-loaded from FastF1
  const wsRef    = useRef(null)
  const retryRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    setStatus('connecting')
    const ws = new WebSocket(`${WS_BASE}/ws/live`)
    wsRef.current = ws
    // Note: don't reset status in onopen — it was already set to 'connecting' above.
    // Status resolves to 'live'/'replay' when the first state message arrives.
    ws.onmessage = e => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'state') {
          setState(msg.data)
          setStatus(msg.data?.is_live ? 'live' : 'replay')
        }
        if (msg.type === 'ping' || msg.type === 'pong') ws.send('ping')
      } catch {}
    }
    ws.onerror  = () => setStatus('offline')
    ws.onclose  = () => {
      setStatus('offline')
      retryRef.current = setTimeout(connect, 4000)
    }
  }, [])

  useEffect(() => {
    connect()
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send('ping')
    }, 20000)
    return () => {
      clearInterval(ping)
      clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Pre-load circuit outline from FastF1 whenever the session GP changes
  useEffect(() => {
    const gp   = state?.session?.gp
    const year = state?.session?.year
    if (!gp || !year) return
    fetch(`${API_BASE}/circuit-layout/${year}/${encodeURIComponent(gp)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.points?.length > 20) setCircuit(d.points) })
      .catch(() => {})
  }, [state?.session?.gp, state?.session?.year])

  const session      = state?.session
  const leaderboard  = state?.leaderboard   || []
  const rcMessages   = state?.race_control  || []
  const radioClips   = state?.team_radio    || []
  const carPositions = state?.car_positions || []
  // Prefer live GPS outline; fall back to FastF1 pre-loaded outline
  const trackOutline = (state?.track_outline?.length > 20 ? state.track_outline : circuitOutline)
  const weather      = state?.weather
  const lapCount     = state?.lap_count     || {}
  const trackStatus  = state?.track_status  || 'AllClear'
  const tsMeta       = TRACK_STATUS_META[trackStatus] || TRACK_STATUS_META.AllClear

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex',
      flexDirection: 'column', fontFamily: 'monospace' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 14px', background: '#0a0d14',
        borderBottom: '1px solid #1e2535', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Radio size={13} style={{ color: '#E8002D' }} />
          <span className="font-mono font-bold" style={{ fontSize: 11, color: '#fff', letterSpacing: 2 }}>
            LIVE PIT WALL
          </span>
          {session && (
            <span className="font-mono" style={{ fontSize: 10, color: '#3d4f66' }}>
              {session.year} · {session.gp?.toUpperCase()} · {session.name?.toUpperCase()}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {lapCount.current > 0 && (
            <span className="font-mono" style={{ fontSize: 10, color: '#3d4f66' }}>
              LAP <span style={{ color: '#8899aa', fontWeight: 700 }}>{lapCount.current}</span>
            </span>
          )}
          <WsStatus status={wsStatus} />
        </div>
      </div>

      {/* Track status banner */}
      {trackStatus !== 'AllClear' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 14px', background: tsMeta.bg,
          borderBottom: `1px solid ${tsMeta.colour}44`, flexShrink: 0,
          animation: 'pulse 1.2s ease-in-out infinite' }}>
          <AlertTriangle size={12} style={{ color: tsMeta.colour }} />
          <span className="font-mono font-bold" style={{ fontSize: 11, color: tsMeta.colour, letterSpacing: 2 }}>
            {tsMeta.label}
          </span>
        </div>
      )}

      {/* Weather */}
      <WeatherStrip wx={weather} />

      {/* Main 3-column grid */}
      <div style={{ flex: 1, display: 'grid',
        gridTemplateColumns: 'minmax(0,1fr) 340px 300px', minHeight: 0 }}>

        {/* LEFT: Leaderboard */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden',
          borderRight: '1px solid #1e2535' }}>
          <div style={{ display: 'grid',
            gridTemplateColumns: '28px 6px 36px 1fr 70px 70px 46px 50px',
            gap: 6, padding: '5px 12px',
            borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0 }}>
            {['POS','','DRV','TEAM','GAP','LAST LAP','TYRE','LAP'].map((h, i) => (
              <span key={i} className="font-mono"
                style={{ fontSize: 8, color: '#2a3545', textAlign: i >= 4 ? 'right' : 'left' }}>
                {h}
              </span>
            ))}
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {leaderboard.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: 200, flexDirection: 'column', gap: 8 }}>
                <Activity size={20} style={{ color: '#1e2535' }} />
                <span className="font-mono" style={{ fontSize: 11, color: '#2a3545' }}>
                  {wsStatus === 'connecting' ? 'CONNECTING TO F1 TIMING...' : 'NO ACTIVE SESSION'}
                </span>
              </div>
            ) : leaderboard.map((drv, i) => (
              <DriverRow key={drv.driver_number} driver={drv} rank={i + 1} isFirst={i === 0} />
            ))}
          </div>
        </div>

        {/* CENTER: Live Track Map */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden',
          borderRight: '1px solid #1e2535' }}>
          <div style={{ padding: '5px 10px', borderBottom: '1px solid #1e2535',
            background: '#0a0d14', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <MapPin size={9} style={{ color: '#3d4f66' }} />
              <span className="font-mono" style={{ fontSize: 8, color: '#3d4f66' }}>TRACK MAP</span>
            </div>
            {carPositions.length > 0 && (
              <span className="font-mono" style={{ fontSize: 7, color: '#3d4f66' }}>
                {carPositions.length} CARS
              </span>
            )}
          </div>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <TrackMap outline={trackOutline} cars={carPositions} wsStatus={wsStatus} />
          </div>
        </div>

        {/* RIGHT: Tabbed RC | Radio */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ display: 'flex', borderBottom: '1px solid #1e2535',
            background: '#0a0d14', flexShrink: 0 }}>
            {[
              { id: 'rc',    icon: <Flag  size={9} />,  label: 'RACE CONTROL', count: rcMessages.length },
              { id: 'radio', icon: <Radio size={9} />,  label: 'RADIO',        count: radioClips.length },
            ].map(tab => (
              <button key={tab.id} onClick={() => setRightTab(tab.id)}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  gap: 4, padding: '6px 8px', cursor: 'pointer',
                  borderBottom: rightTab === tab.id ? '2px solid #E8002D' : '2px solid transparent',
                  background: rightTab === tab.id ? 'rgba(232,0,45,0.05)' : 'transparent',
                  color: rightTab === tab.id ? '#c0cfe0' : '#3d4f66',
                }}>
                <span style={{ color: 'inherit' }}>{tab.icon}</span>
                <span className="font-mono" style={{ fontSize: 8, fontWeight: 700, letterSpacing: 1 }}>
                  {tab.label}
                </span>
                {tab.count > 0 && (
                  <span className="font-mono" style={{ fontSize: 7,
                    background: rightTab === tab.id ? 'rgba(232,0,45,0.2)' : '#1e2535',
                    color: rightTab === tab.id ? '#E8002D' : '#3d4f66',
                    padding: '1px 4px', borderRadius: 2 }}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {rightTab === 'rc' ? (
              rcMessages.length === 0 ? (
                <div style={{ padding: 16, textAlign: 'center' }}>
                  <span className="font-mono" style={{ fontSize: 9, color: '#2a3545' }}>NO MESSAGES</span>
                </div>
              ) : rcMessages.map((msg, i) => <RcMessage key={i} msg={msg} />)
            ) : (
              radioClips.length === 0 ? (
                <div style={{ padding: 16, textAlign: 'center',
                  display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
                  <Radio size={16} style={{ color: '#1e2535' }} />
                  <span className="font-mono" style={{ fontSize: 9, color: '#2a3545' }}>
                    {wsStatus === 'live' ? 'AWAITING RADIO CLIPS' : 'NO RADIO CLIPS'}
                  </span>
                  <span className="font-mono" style={{ fontSize: 8, color: '#1e2535' }}>
                    {wsStatus === 'live'
                      ? 'Teams broadcast during live sessions'
                      : 'Radio available during live sessions only'}
                  </span>
                </div>
              ) : radioClips.map((clip, i) => (
                <RadioClip key={clip.recording_url || i} clip={clip} />
              ))
            )}
          </div>
        </div>

      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.65} }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e2535; border-radius: 2px; }
      `}</style>
    </div>
  )
}
