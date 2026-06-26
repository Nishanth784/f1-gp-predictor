import { useRef, useEffect, useState } from 'react'
import { getTeamColour } from './TeamColours'

// Recognisable simplified circuit outlines — viewBox 0 0 240 220
const CIRCUITS = {
  monaco: "M68,18 L155,18 C178,18 192,32 192,52 L192,80 C192,95 183,106 170,110 L152,113 C138,116 128,126 126,142 L124,154 C122,166 113,173 100,173 L75,173 C58,173 46,162 42,148 L38,130 C32,110 40,92 56,85 L69,80 C80,76 86,67 84,55 L82,38 C80,27 74,18 68,18 Z",
  silverstone: "M40,52 C36,35 50,18 70,18 L168,18 C190,18 206,32 208,54 L212,82 C215,100 205,116 188,122 L172,126 C158,130 148,142 146,158 C144,172 152,184 166,186 C180,188 190,178 192,164 L195,150 C198,136 192,122 178,116 L166,112 C150,106 140,92 138,74 L136,58 C132,42 120,32 102,30 L82,28 C62,26 44,38 40,52 Z",
  monza: "M28,38 L212,38 C218,38 224,44 224,50 L224,78 L180,78 L180,95 L224,95 L224,168 C224,175 218,180 212,180 L28,180 C22,180 16,175 16,168 L16,140 L60,140 L60,123 L16,123 L16,50 C16,44 22,38 28,38 Z",
  bahrain: "M120,18 C155,16 190,36 208,68 C226,100 222,138 205,162 C188,186 162,196 135,192 L115,188 C98,185 85,174 80,160 C75,146 78,130 88,120 L96,112 C108,100 112,84 106,70 C100,56 86,50 72,54 C58,58 50,72 52,86 L54,98 C58,114 52,128 40,136 C28,144 14,140 10,126 C6,112 14,96 26,84 L38,72 C55,48 85,20 120,18 Z",
  "abu dhabi": "M38,72 L82,28 C98,12 122,8 146,20 L196,48 C214,60 220,84 214,108 L200,148 C188,170 164,182 140,178 L120,175 C105,173 95,165 90,153 L86,140 C82,126 86,112 96,106 L110,100 C122,94 128,82 124,70 C120,58 108,52 96,56 C84,60 78,72 80,84 L82,96 C84,110 78,122 66,128 C54,134 40,128 34,116 C28,104 32,88 38,72 Z",
  suzuka: "M60,22 L155,22 C178,22 194,38 194,62 L194,96 L132,96 L132,118 L194,118 L194,156 C194,178 178,196 155,196 L60,196 C37,196 20,178 20,156 L20,128 L78,128 L78,108 L20,108 L20,62 C20,38 37,22 60,22 Z",
  spa: "M30,80 L72,24 C88,6 114,2 138,14 L190,42 C215,56 225,84 218,112 L208,152 C198,178 174,192 148,188 L105,180 C80,174 65,156 62,130 L60,115 C58,100 65,88 76,84 L88,80 C100,76 108,66 106,54 C104,42 94,34 82,36 L68,38 C52,40 36,54 30,80 Z",
  singapore: "M55,82 L80,38 C92,18 116,10 140,20 L188,46 C210,58 218,82 212,108 L205,138 C198,160 178,174 155,172 L135,170 C118,168 107,158 103,144 L100,130 C96,116 100,102 110,96 L122,90 C134,84 140,72 136,60 C132,48 120,42 108,46 L96,50 C80,56 65,68 55,82 Z",
  austria: "M55,55 L175,55 C195,55 208,68 208,88 L208,132 C208,152 195,165 175,165 L55,165 C35,165 22,152 22,132 L22,88 C22,68 35,55 55,55 Z",
  zandvoort: "M48,58 C44,38 60,20 82,20 L158,20 C180,20 198,36 200,58 L202,88 C204,108 194,126 178,134 L175,158 C174,172 162,182 148,182 L92,182 C78,182 66,172 65,158 L62,134 C46,126 38,108 40,88 Z",
  hungary: "M62,50 C55,32 68,16 88,16 L152,16 C172,16 184,30 186,50 L188,80 C190,100 180,118 164,126 L148,134 C132,142 122,158 124,176 L126,190 L114,192 L102,190 L104,176 C106,158 96,142 80,134 L64,126 C48,118 38,100 40,80 Z",
  brazil: "M120,16 C145,14 170,28 182,52 C194,76 192,105 178,126 C164,148 142,160 118,160 L98,160 C82,160 68,152 60,140 L40,110 C28,90 28,65 40,48 C52,30 75,18 100,16 Z",
  baku: "M28,50 L200,50 C215,50 224,60 224,75 L224,145 C224,160 215,170 200,170 L140,170 L140,150 L105,150 L105,170 L28,170 C14,170 6,160 6,145 L6,75 C6,60 14,50 28,50 Z",
  jeddah: "M36,22 L204,22 C214,22 222,30 222,40 L222,70 L185,70 L185,88 L222,88 L222,160 C222,170 214,178 204,178 L36,178 C26,178 18,170 18,160 L18,128 L55,128 L55,110 L18,110 L18,40 C18,30 26,22 36,22 Z",
  cota: "M45,30 L170,30 C190,30 206,42 210,62 L215,90 L195,90 L195,112 L215,112 L215,145 C215,168 200,184 178,186 L88,190 C65,192 46,178 40,156 L26,112 C18,88 24,62 38,44 Z",
  miami: "M50,40 L175,40 C198,40 214,55 216,78 L218,108 L185,108 L185,128 L218,128 L218,155 C218,175 203,188 182,188 L58,188 C36,188 20,173 18,152 L14,118 L48,118 L48,98 L14,98 L14,62 C16,50 30,40 50,40 Z",
  "las vegas": "M20,50 L220,50 C228,50 234,56 234,64 L234,92 L190,92 L190,110 L234,110 L234,155 C234,164 228,170 220,170 L20,170 C12,170 6,164 6,155 L6,126 L50,126 L50,108 L6,108 L6,64 C6,56 12,50 20,50 Z",
  mexico: "M45,45 C38,28 52,12 72,12 L168,12 C188,12 202,26 205,46 L210,80 L185,80 L185,100 L210,100 L212,135 C214,158 200,174 178,176 L62,176 C40,176 26,162 24,140 L22,105 L48,105 L48,85 L22,85 Z",
  china: "M50,35 L175,35 C198,35 215,50 218,73 L220,105 L192,105 L192,125 L220,125 L220,155 C220,175 204,188 182,188 L58,188 C36,188 20,175 18,155 L18,125 L46,125 L46,105 L18,105 L18,73 C20,50 28,35 50,35 Z",
  australia: "M55,48 C48,30 62,14 82,14 L158,14 C180,14 196,30 198,52 L202,82 L175,82 L175,100 L202,100 L205,135 C208,158 194,175 172,178 L68,178 C46,178 30,162 28,140 L24,108 L52,108 L52,88 L24,88 Z",
  default: "M55,45 C48,28 62,12 84,12 L156,12 C178,12 196,28 200,50 L205,85 L180,85 L180,102 L205,102 L208,140 C210,163 196,178 174,180 L66,180 C44,180 28,165 26,143 L22,108 L48,108 L48,90 L22,90 Z",
}

function getPath(gpName) {
  const lower = (gpName || '').toLowerCase()
  for (const [key, path] of Object.entries(CIRCUITS)) {
    if (key !== 'default' && lower.includes(key)) return path
  }
  // secondary keyword checks
  if (lower.includes('grand prix de monaco') || lower.includes('monte')) return CIRCUITS.monaco
  if (lower.includes('interlagos') || lower.includes('são paulo') || lower.includes('sao paulo')) return CIRCUITS.brazil
  if (lower.includes('yas')) return CIRCUITS['abu dhabi']
  if (lower.includes('albert park') || lower.includes('melbourne')) return CIRCUITS.australia
  if (lower.includes('hungar')) return CIRCUITS.hungary
  if (lower.includes('dutch') || lower.includes('netherlands')) return CIRCUITS.zandvoort
  if (lower.includes('belgian')) return CIRCUITS.spa
  if (lower.includes('japanese')) return CIRCUITS.suzuka
  if (lower.includes('british')) return CIRCUITS.silverstone
  if (lower.includes('italian')) return CIRCUITS.monza
  if (lower.includes('saudi') || lower.includes('jeddah')) return CIRCUITS.jeddah
  if (lower.includes('vegas')) return CIRCUITS['las vegas']
  if (lower.includes('singapore') || lower.includes('marina bay')) return CIRCUITS.singapore
  if (lower.includes('austrian') || lower.includes('styrian') || lower.includes('red bull ring')) return CIRCUITS.austria
  if (lower.includes('emilia') || lower.includes('imola')) return CIRCUITS.default
  if (lower.includes('miami')) return CIRCUITS.miami
  return CIRCUITS.default
}

export default function CircuitMap({ gpName = '', drivers = [], width = 240, height = 220 }) {
  const pathRef  = useRef(null)
  const svgRef   = useRef(null)
  const [dots, setDots] = useState([])
  const circuitPath = getPath(gpName)

  // Recompute dot positions when path or driver count changes
  useEffect(() => {
    // Wait a tick for the DOM path to paint
    const id = setTimeout(() => {
      if (!pathRef.current) return
      const totalLen = pathRef.current.getTotalLength()
      if (!totalLen) return
      const n = drivers.length
      setDots(
        drivers.map((drv, i) => {
          const t   = (i / Math.max(n, 1)) * totalLen
          const pt  = pathRef.current.getPointAtLength(t)
          return { x: pt.x, y: pt.y, drv }
        })
      )
    }, 50)
    return () => clearTimeout(id)
  }, [circuitPath, drivers.length])

  return (
    <div style={{ position: 'relative', width, height }}>
      <svg ref={svgRef} viewBox="0 0 240 220" width={width} height={height}
        style={{ display: 'block' }}>
        <defs>
          <filter id="glow-dot">
            <feGaussianBlur stdDeviation="2" result="b" />
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="glow-p1">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* Track: shadow → asphalt → centre dash */}
        <path d={circuitPath} fill="none" stroke="#0d1824" strokeWidth={14}
          strokeLinecap="round" strokeLinejoin="round" />
        <path d={circuitPath} fill="none" stroke="#1e2d42" strokeWidth={9}
          strokeLinecap="round" strokeLinejoin="round" />
        <path d={circuitPath} fill="none" stroke="#2a3d58" strokeWidth={4}
          strokeLinecap="round" strokeLinejoin="round" />
        <path ref={pathRef} d={circuitPath} fill="none"
          stroke="#334d6e" strokeWidth={1.5}
          strokeDasharray="4 8" strokeLinecap="round" strokeLinejoin="round"
          opacity={0.5} />

        {/* Driver dots */}
        {dots.map(({ x, y, drv }, i) => {
          const colour = getTeamColour(drv.team || drv.Team || '')
          const code   = (drv.driver || drv.Driver || '').slice(0, 3).toUpperCase()
          const isP1   = i === 0
          const r      = isP1 ? 6 : 4
          return (
            <g key={code + i}>
              {isP1 && (
                <circle cx={x} cy={y} r={10} fill="none"
                  stroke={colour} strokeWidth={1.5} opacity={0.45}
                  style={{ animation: 'ring-pulse 1.8s ease-out infinite' }} />
              )}
              <circle cx={x} cy={y} r={r} fill={colour}
                filter={isP1 ? 'url(#glow-p1)' : 'url(#glow-dot)'} />
              <text x={x} y={y - r - 3} textAnchor="middle"
                fontSize={isP1 ? 7 : 5.5} fontFamily="monospace"
                fontWeight="bold" fill={colour} opacity={0.95}>
                {code}
              </text>
            </g>
          )
        })}

        {drivers.length === 0 && (
          <text x="120" y="115" textAnchor="middle" fontSize="9"
            fontFamily="monospace" fill="#3d4f66">
            SELECT RACE TO LOAD
          </text>
        )}
      </svg>
    </div>
  )
}
