import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Play, Pause, SkipBack, Loader, Flag, AlertTriangle, Wifi, WifiOff, Zap } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'
import { parseRouteParams } from '../utils/sanitizeParams'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

// Derive WebSocket base from HTTP API base
const WS_BASE = API_BASE.replace(/^http/, 'ws')

const SECTOR_COLOURS = {
  purple: '#bf5af2',
  green:  '#00ff88',
  yellow: '#FFD700',
  grey:   '#3d4f66',
}

const TYRE_DISPLAY = {
  SOFT:    { colour: '#E8002D', label: 'S' },
  MEDIUM:  { colour: '#FFD700', label: 'M' },
  HARD:    { colour: '#FFFFFF', label: 'H' },
  INTER:   { colour: '#43b02a', label: 'I' },
  WET:     { colour: '#0067ff', label: 'W' },
  UNKNOWN: { colour: '#3d4f66', label: '?' },
}

const RC_ICONS = {
  SafetyCar:        { icon: '🚗', colour: '#FFD700', label: 'SC' },
  VirtualSafetyCar: { icon: '🟡', colour: '#FFD700', label: 'VSC' },
  Flag:             { icon: '🏁', colour: '#fff',    label: 'FLAG' },
  Drs:              { icon: '▲',  colour: '#00ff88', label: 'DRS' },
  Incident:         { icon: '⚠',  colour: '#FF8000', label: 'INC' },
  Other:            { icon: '📻', colour: '#3d4f66', label: 'MSG' },
}

// WebSocket connection states
const WS_IDLE        = 'idle'
const WS_CONNECTING  = 'connecting'
const WS_LOADING     = 'loading'      // FastF1 loading on server
const WS_READY       = 'ready'        // connected, waiting for "start"
const WS_STREAMING   = 'streaming'
const WS_FINISHED    = 'finished'
const WS_ERROR       = 'error'

const WS_STATUS_LABELS = {
  [WS_IDLE]:       { label: 'OFFLINE', colour: '#3d4f66' },
  [WS_CONNECTING]: { label: 'CONNECTING…', colour: '#FFD700' },
  [WS_LOADING]:    { label: 'LOADING SESSION…', colour: '#FFD700' },
  [WS_READY]:      { label: 'READY', colour: '#00ff88' },
  [WS_STREAMING]:  { label: 'LIVE', colour: '#E8002D' },
  [WS_FINISHED]:   { label: 'FINISHED', colour: '#00ff88' },
  [WS_ERROR]:      { label: 'ERROR', colour: '#E8002D' },
}

const SPEEDS = [
  { label: '1×',  value: 1 },
  { label: '5×',  value: 5 },
  { label: '20×', value: 20 },
]

// ─── Sub-components ──────────────────────────────────────────────────────────

function TyreChip({ compound }) {
  const t = TYRE_DISPLAY[compound] || TYRE_DISPLAY.UNKNOWN
  return (
    <div style={{ width: 18, height: 18, borderRadius: '50%',
      background: t.colour, display: 'flex', alignItems: 'center',
      justifyContent: 'center', flexShrink: 0,
      border: '1px solid rgba(0,0,0,0.4)' }}>
      <span style={{ fontFamily: 'monospace', fontSize: 8, fontWeight: 700, color: '#000' }}>
        {t.label}
      </span>
    </div>
  )
}

function SectorCell({ ms, colour }) {
  if (!ms) return <span style={{ color: '#3d4f66', fontFamily: 'monospace', fontSize: 9 }}>--.-</span>
  const s = (ms / 1000).toFixed(3)
  return (
    <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 600,
      color: SECTOR_COLOURS[colour] || '#8899aa' }}>
      {s}
    </span>
  )
}

function RCBadge({ msg }) {
  const cat = msg.category || 'Other'
  const info = RC_ICONS[cat] || RC_ICONS.Other
  const isFlag = cat === 'Flag'
  const flagColour = isFlag
    ? (msg.flag === 'RED' ? '#E8002D' : msg.flag === 'YELLOW' ? '#FFD700'
      : msg.flag === 'GREEN' ? '#00ff88' : msg.flag === 'CHEQUERED' ? '#fff' : info.colour)
    : info.colour

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
      background: `${flagColour}11`, borderLeft: `3px solid ${flagColour}`,
      borderRadius: '0 4px 4px 0', marginBottom: 4 }}>
      <span style={{ fontSize: 12 }}>{info.icon}</span>
      <div>
        <div style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: flagColour }}>
          {isFlag ? (msg.flag || 'FLAG') : info.label}
          {msg.lap ? ` · LAP ${msg.lap}` : ''}
        </div>
        <div style={{ fontFamily: 'monospace', fontSize: 8, color: '#8899aa', marginTop: 1 }}>
          {msg.message?.slice(0, 80)}
        </div>
      </div>
    </div>
  )
}

function WsStatusBadge({ status }) {
  const s = WS_STATUS_LABELS[status] || WS_STATUS_LABELS[WS_IDLE]
  const isPulsing = status === WS_STREAMING
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px',
      border: `1px solid ${s.colour}44`, borderRadius: 3,
      background: `${s.colour}11` }}>
      <div style={{
        width: 6, height: 6, borderRadius: '50%', background: s.colour,
        animation: isPulsing ? 'ring-pulse 1.2s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontFamily: 'monospace', fontSize: 8, fontWeight: 700, color: s.colour }}>
        {s.label}
      </span>
    </div>
  )
}

// ─── Timing row (shared between REST and WS modes) ────────────────────────────

function DriverRow({ row, i }) {
  const colour = getTeamColour(row.team || '')
  const isPit  = row.is_pit_lap
  return (
    <div style={{ display: 'grid', padding: '6px 10px',
      gridTemplateColumns: '28px 10px 30px 50px 1fr 60px 60px 60px 22px 60px',
      gap: 4, borderBottom: '1px solid rgba(255,255,255,0.04)',
      background: isPit ? 'rgba(255,215,0,0.04)' : i < 3 ? 'rgba(255,255,255,0.015)' : 'transparent',
      alignItems: 'center' }}>

      <span style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
        color: i === 0 ? '#FFD700' : i === 1 ? '#C0C0C0' : i === 2 ? '#CD7F32' : '#8899aa' }}>
        P{row.position || i + 1}
      </span>

      <div style={{ width: 6, height: 6, borderRadius: '50%', background: colour,
        boxShadow: `0 0 4px ${colour}88` }} />

      <span style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: colour }}>
        {row.driver}
      </span>

      <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {(row.team || '').replace('Racing', '').replace('F1 Team', '').trim().slice(0, 8)}
      </span>

      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <TyreChip compound={row.compound || 'UNKNOWN'} />
        {isPit && (
          <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#FFD700',
            background: 'rgba(255,215,0,0.15)', padding: '1px 4px', borderRadius: 2 }}>
            PIT
          </span>
        )}
        <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66' }}>
          {row.tyre_life > 0 ? `${row.tyre_life}L` : ''}
        </span>
      </div>

      <span style={{ fontFamily: 'monospace', fontSize: 10,
        color: row.lap_time_fmt ? '#fff' : '#3d4f66' }}>
        {row.lap_time_fmt || '--:--.---'}
      </span>

      <SectorCell ms={row.sector1_ms} colour={row.s1_colour} />
      <SectorCell ms={row.sector2_ms} colour={row.s2_colour} />
      <SectorCell ms={row.sector3_ms} colour={row.s3_colour} />

      <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#8899aa', textAlign: 'right' }}>
        {i === 0 ? 'LEADER'
          : row.gap_to_leader != null ? `+${row.gap_to_leader.toFixed(3)}` : '--'}
      </span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function TimingTower() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  // ── REST mode state ──
  const [data, setData]         = useState(null)
  const [lap, setLap]           = useState(1)
  const [snapshot, setSnapshot] = useState([])
  const [rcEvents, setRcEvents] = useState([])
  const [playing, setPlaying]   = useState(false)
  const [loading, setLoading]   = useState(false)
  const [loadMsg, setLoadMsg]   = useState('')
  const [sessionType, setSessionType] = useState('R')
  const playRef = useRef(null)

  // ── WebSocket mode state ──
  const [liveMode, setLiveMode]       = useState(false)
  const [wsStatus, setWsStatus]       = useState(WS_IDLE)
  const [wsLap, setWsLap]             = useState(0)
  const [wsTotalLaps, setWsTotalLaps] = useState(0)
  const [wsSnapshot, setWsSnapshot]   = useState([])
  const [wsRcEvents, setWsRcEvents]   = useState([])
  const [wsMsg, setWsMsg]             = useState('')
  const [speed, setSpeed]             = useState(5)
  const wsRef = useRef(null)

  // ─── REST: Load session ───────────────────────────────────────────────────

  const loadData = useCallback(() => {
    if (!year || !gpDecoded) return
    setLoading(true)
    setLoadMsg('Loading session from FastF1 — may take up to 90 s on first load…')
    fetch(`${API_BASE}/timing/${year}/${encodeURIComponent(gpDecoded)}?session_type=${sessionType}`)
      .then(r => r.json())
      .then(d => {
        if (d.detail) throw new Error(d.detail)
        setData(d)
        setLap(1)
        setLoading(false)
        setLoadMsg('')
      })
      .catch(e => { setLoadMsg(`Error: ${e.message}`); setLoading(false) })
  }, [year, gpDecoded, sessionType])

  // REST: build snapshot when data or lap changes
  useEffect(() => {
    if (!data?.laps) return
    const byDriver = {}
    for (const l of data.laps) {
      if (l.lap_number > lap) continue
      const prev = byDriver[l.driver]
      if (!prev || l.lap_number > prev.lap_number) byDriver[l.driver] = l
    }
    const snap = Object.values(byDriver).sort((a, b) =>
      (a.position || 99) - (b.position || 99) || a.driver.localeCompare(b.driver)
    )
    setSnapshot(snap)
    setRcEvents((data.race_control || []).filter(m => (m.lap || 0) <= lap))
  }, [data, lap])

  // REST: playback timer
  useEffect(() => {
    if (!playing || !data || liveMode) return
    const total = data.total_laps || 1
    if (lap >= total) { setPlaying(false); return }
    playRef.current = setTimeout(() => setLap(l => l + 1), 800)
    return () => clearTimeout(playRef.current)
  }, [playing, lap, data, liveMode])

  // ─── WebSocket: connect / disconnect ─────────────────────────────────────

  const connectWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setWsStatus(WS_CONNECTING)
    setWsMsg('')
    setWsLap(0)
    setWsSnapshot([])
    setWsRcEvents([])

    const url = `${WS_BASE}/ws/timing/${year}/${encodeURIComponent(gpDecoded)}?session_type=${sessionType}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setWsStatus(WS_LOADING)
      setWsMsg('WebSocket connected — waiting for session data from FastF1…')
    }

    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }

      switch (msg.status) {
        case 'loading':
          setWsStatus(WS_LOADING)
          setWsMsg(msg.message || 'Loading…')
          break

        case 'ready':
          setWsStatus(WS_READY)
          setWsTotalLaps(msg.total_laps || 0)
          setWsMsg(`Session ready — ${msg.total_laps} laps. Starting replay at ${speed}×…`)
          // Tell server to start streaming
          ws.send(JSON.stringify({ action: 'start', speed }))
          setTimeout(() => setWsStatus(WS_STREAMING), 200)
          break

        case 'lap':
          setWsStatus(WS_STREAMING)
          setWsLap(msg.lap)
          setWsMsg('')
          // Sort snapshot by position
          const snap = [...(msg.snapshot || [])].sort(
            (a, b) => (a.position || 99) - (b.position || 99)
          )
          setWsSnapshot(snap)
          setWsRcEvents(prev => [...prev, ...(msg.race_control || [])])
          break

        case 'finished':
          setWsStatus(WS_FINISHED)
          setWsMsg('Replay complete.')
          break

        case 'error':
          setWsStatus(WS_ERROR)
          setWsMsg(msg.message || 'Unknown error')
          break

        default:
          break
      }
    }

    ws.onerror = () => {
      setWsStatus(WS_ERROR)
      setWsMsg('WebSocket connection failed. Is the backend running?')
    }

    ws.onclose = (e) => {
      if (e.code !== 1000 && wsRef.current) {
        // Unexpected close
        setWsStatus(prev => prev === WS_FINISHED ? WS_FINISHED : WS_ERROR)
      }
    }
  }, [year, gpDecoded, sessionType, speed])

  const disconnectWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected')
      wsRef.current = null
    }
    setWsStatus(WS_IDLE)
    setWsMsg('')
  }, [])

  // Auto-connect when live mode toggled on; disconnect when toggled off
  useEffect(() => {
    if (liveMode) {
      connectWs()
    } else {
      disconnectWs()
    }
    return () => { if (!liveMode) disconnectWs() }
  }, [liveMode])  // eslint-disable-line

  // Cleanup on unmount
  useEffect(() => () => disconnectWs(), [])  // eslint-disable-line

  // ─── Derived display state (REST vs WS) ──────────────────────────────────

  const displaySnapshot = liveMode ? wsSnapshot : snapshot
  const displayRcRecent = liveMode
    ? [...wsRcEvents].reverse().slice(0, 12)
    : [...(data?.race_control || [])].reverse().slice(0, 12)
  const displayLap      = liveMode ? wsLap : lap
  const displayTotal    = liveMode ? wsTotalLaps : (data?.total_laps || 1)
  const rcThisLap       = liveMode
    ? wsRcEvents.filter(m => (m.lap || 0) === wsLap)
    : (data?.race_control || []).filter(m => (m.lap || 0) === lap)
  const statusMsg = liveMode ? wsMsg : loadMsg

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      {/* Controls bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px',
        borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0, flexWrap: 'wrap' }}>

        {/* Session type selector */}
        {['R','Q','FP1','FP2','FP3'].map(st => (
          <button key={st} onClick={() => { setSessionType(st); if (liveMode) setLiveMode(false) }}
            style={{ padding: '3px 10px', borderRadius: 3, cursor: 'pointer',
              fontFamily: 'monospace', fontSize: 9, fontWeight: 700,
              border: `1px solid ${sessionType === st ? '#E8002D' : '#1e2535'}`,
              background: sessionType === st ? 'rgba(232,0,45,0.15)' : 'transparent',
              color: sessionType === st ? '#E8002D' : '#3d4f66' }}>
            {st}
          </button>
        ))}

        <div style={{ width: 1, height: 20, background: '#1e2535' }} />

        {/* REST load button */}
        {!liveMode && (
          <button onClick={loadData} disabled={loading}
            style={{ padding: '4px 14px', borderRadius: 4, cursor: loading ? 'not-allowed' : 'pointer',
              fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
              background: '#E8002D', color: '#fff', border: 'none', opacity: loading ? 0.6 : 1 }}>
            {loading ? 'LOADING…' : 'LOAD SESSION'}
          </button>
        )}

        {/* LIVE toggle */}
        <button
          onClick={() => setLiveMode(m => !m)}
          title={liveMode ? 'Disconnect WebSocket' : 'Start WebSocket live replay'}
          style={{ display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 12px', borderRadius: 4, cursor: 'pointer',
            fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
            border: `1px solid ${liveMode ? '#00ff88' : '#1e2535'}`,
            background: liveMode ? 'rgba(0,255,136,0.12)' : 'transparent',
            color: liveMode ? '#00ff88' : '#3d4f66' }}>
          {liveMode ? <Wifi size={11} /> : <WifiOff size={11} />}
          {liveMode ? 'LIVE ON' : 'LIVE'}
        </button>

        {/* Speed selector (shown in live mode) */}
        {liveMode && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66' }}>SPEED</span>
            {SPEEDS.map(s => (
              <button key={s.value}
                onClick={() => setSpeed(s.value)}
                style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                  fontFamily: 'monospace', fontSize: 8, fontWeight: 700,
                  border: `1px solid ${speed === s.value ? '#bf5af2' : '#1e2535'}`,
                  background: speed === s.value ? 'rgba(191,90,242,0.15)' : 'transparent',
                  color: speed === s.value ? '#bf5af2' : '#3d4f66' }}>
                {s.label}
              </button>
            ))}
          </div>
        )}

        {/* WS status badge */}
        {liveMode && <WsStatusBadge status={wsStatus} />}

        {/* REST playback controls */}
        {!liveMode && data && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button onClick={() => { setLap(1); setPlaying(false) }}
              style={{ background: 'transparent', border: '1px solid #1e2535', borderRadius: 4,
                padding: '3px 8px', cursor: 'pointer', color: '#3d4f66' }}>
              <SkipBack size={10} />
            </button>
            <button onClick={() => setPlaying(p => !p)}
              style={{ background: playing ? '#E8002D' : 'transparent',
                border: `1px solid ${playing ? '#E8002D' : '#1e2535'}`,
                borderRadius: 4, padding: '3px 10px', cursor: 'pointer',
                color: playing ? '#fff' : '#3d4f66',
                display: 'flex', alignItems: 'center', gap: 4 }}>
              {playing ? <Pause size={10} /> : <Play size={10} />}
              <span style={{ fontFamily: 'monospace', fontSize: 9 }}>
                {playing ? 'PAUSE' : 'PLAY'}
              </span>
            </button>
          </div>
        )}

        {/* Reconnect button when WS errored/finished */}
        {liveMode && (wsStatus === WS_ERROR || wsStatus === WS_FINISHED) && (
          <button onClick={connectWs}
            style={{ padding: '3px 10px', borderRadius: 3, cursor: 'pointer',
              fontFamily: 'monospace', fontSize: 9, fontWeight: 700,
              border: '1px solid #FFD700', background: 'rgba(255,215,0,0.1)',
              color: '#FFD700', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Zap size={10} />
            RECONNECT
          </button>
        )}

        {/* REST: Lap scrubber */}
        {!liveMode && data && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 200 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#E8002D', fontWeight: 700 }}>
              LAP {lap}
            </span>
            <input type="range" min={1} max={displayTotal} value={lap}
              onChange={e => { setLap(parseInt(e.target.value)); setPlaying(false) }}
              style={{ flex: 1 }} />
            <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#3d4f66' }}>/{displayTotal}</span>
          </div>
        )}

        {/* WS: progress indicator */}
        {liveMode && wsStatus === WS_STREAMING && wsTotalLaps > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 180 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#E8002D', fontWeight: 700 }}>
              LAP {wsLap}
            </span>
            <div style={{ flex: 1, height: 3, background: '#1e2535', borderRadius: 2 }}>
              <div style={{
                width: `${(wsLap / wsTotalLaps) * 100}%`,
                height: '100%', background: '#E8002D', borderRadius: 2,
                transition: 'width 0.5s ease',
              }} />
            </div>
            <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#3d4f66' }}>/{wsTotalLaps}</span>
          </div>
        )}

        {loading && !liveMode &&
          <Loader size={12} style={{ color: '#E8002D', animation: 'spin 1s linear infinite' }} />}
      </div>

      {/* Status / loading message */}
      {statusMsg && (
        <div style={{ padding: '7px 16px', flexShrink: 0,
          background: wsStatus === WS_ERROR ? 'rgba(232,0,45,0.08)' : 'rgba(255,215,0,0.05)',
          borderBottom: `1px solid ${wsStatus === WS_ERROR ? 'rgba(232,0,45,0.2)' : 'rgba(255,215,0,0.15)'}` }}>
          <span style={{ fontFamily: 'monospace', fontSize: 10,
            color: wsStatus === WS_ERROR ? '#E8002D' : '#FFD700' }}>
            {statusMsg}
          </span>
        </div>
      )}

      {/* RC alert for current lap */}
      {rcThisLap.length > 0 && (
        <div style={{ padding: '6px 16px', background: 'rgba(255,215,0,0.08)',
          borderBottom: '1px solid rgba(255,215,0,0.2)',
          display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
          <AlertTriangle size={11} style={{ color: '#FFD700' }} />
          {rcThisLap.slice(0, 3).map((m, i) => (
            <span key={i} style={{ fontFamily: 'monospace', fontSize: 10, color: '#FFD700' }}>
              {m.category}: {m.message?.slice(0, 60)}
            </span>
          ))}
        </div>
      )}

      {/* Main grid */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 240px',
        gap: 8, padding: 10, minHeight: 0, overflow: 'hidden' }}>

        {/* Timing tower */}
        <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
          display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* Lap counter (live mode) */}
          {liveMode && wsStatus === WS_STREAMING && (
            <div style={{ padding: '4px 12px', background: 'rgba(232,0,45,0.08)',
              borderBottom: '1px solid rgba(232,0,45,0.2)',
              display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#E8002D',
                animation: 'ring-pulse 1.2s ease-in-out infinite' }} />
              <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: '#E8002D' }}>
                LIVE · LAP {wsLap} / {wsTotalLaps} · {speed}× SPEED
              </span>
            </div>
          )}

          {/* Header row */}
          <div style={{ display: 'grid', padding: '5px 10px',
            gridTemplateColumns: '28px 10px 30px 50px 1fr 60px 60px 60px 22px 60px',
            gap: 4, borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0 }}>
            {['POS','','DRV','TEAM','','LAP TIME','S1','S2','S3','GAP'].map((h, i) => (
              <span key={i} style={{ fontFamily: 'monospace', fontSize: 7,
                color: '#3d4f66', letterSpacing: '0.1em' }}>{h}</span>
            ))}
          </div>

          {/* Driver rows */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {displaySnapshot.length === 0 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#3d4f66' }}>
                  {liveMode
                    ? (wsStatus === WS_CONNECTING || wsStatus === WS_LOADING
                      ? 'CONNECTING…'
                      : wsStatus === WS_READY ? 'STARTING REPLAY…'
                      : 'ENABLE LIVE MODE OR LOAD SESSION')
                    : 'SELECT SESSION TYPE AND CLICK LOAD SESSION'}
                </span>
              </div>
            )}
            {displaySnapshot.map((row, i) => (
              <DriverRow key={row.driver} row={row} i={i} />
            ))}
          </div>
        </div>

        {/* Right: Race control feed */}
        <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
          display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '6px 12px', borderBottom: '1px solid #1e2535',
            background: '#0a0d14', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66',
              letterSpacing: '0.12em' }}>RACE CONTROL</span>
            {liveMode && <WsStatusBadge status={wsStatus} />}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
            {displayRcRecent.length === 0 && (
              <div style={{ fontFamily: 'monospace', fontSize: 8, color: '#3d4f66',
                textAlign: 'center', marginTop: 24 }}>
                {liveMode ? 'WAITING FOR MESSAGES…' : 'LOAD SESSION TO SEE MESSAGES'}
              </div>
            )}
            {displayRcRecent.map((m, i) => <RCBadge key={i} msg={m} />)}
          </div>

          {/* Sector legend */}
          <div style={{ padding: '8px 10px', borderTop: '1px solid #1e2535', flexShrink: 0 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
              marginBottom: 5, letterSpacing: '0.1em' }}>SECTOR COLOURS</div>
            {Object.entries(SECTOR_COLOURS).filter(([k]) => k !== 'grey').map(([k, v]) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <div style={{ width: 8, height: 8, borderRadius: 1, background: v }} />
                <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66',
                  textTransform: 'uppercase' }}>{k}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
