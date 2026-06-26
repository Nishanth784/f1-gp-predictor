export const TEAM_COLOURS = {
  'Red Bull Racing': '#3671C6',
  'Red Bull':        '#3671C6',
  'Ferrari':         '#E8002D',
  'McLaren':         '#FF8000',
  'Mercedes':        '#27F4D2',
  'Aston Martin':    '#229971',
  'Alpine':          '#FF87BC',
  'Williams':        '#64C4FF',
  'RB':              '#6692FF',
  'Racing Bulls':    '#6692FF',
  'Visa Cash App RB':'#6692FF',
  'AlphaTauri':      '#6692FF',
  'Kick Sauber':     '#52E252',
  'Sauber':          '#52E252',
  'Haas F1 Team':    '#B6BABD',
  'Haas':            '#B6BABD',
  'Alfa Romeo':      '#900000',
  'Racing Point':    '#F596C8',
  'Force India':     '#F596C8',
  'Renault':         '#FFF500',
  'Toro Rosso':      '#469BFF',
}

export function getTeamColour(team = '') {
  if (!team) return '#8899aa'
  // exact match
  if (TEAM_COLOURS[team]) return TEAM_COLOURS[team]
  // case-insensitive partial match
  const lower = team.toLowerCase()
  for (const [k, v] of Object.entries(TEAM_COLOURS)) {
    if (lower.includes(k.toLowerCase()) || k.toLowerCase().includes(lower)) return v
  }
  return '#8899aa'
}

export const SECTOR_COLOURS = {
  personal_best: '#00FF00',
  overall_best:  '#CC00FF',
  slower:        '#FFD700',
  pit:           '#FF4444',
}

export const TYRE_COLOURS = {
  SOFT:         '#E8002D',
  MEDIUM:       '#FFD700',
  HARD:         '#FFFFFF',
  INTERMEDIATE: '#39B54A',
  WET:          '#0067FF',
}

export function getTyreColour(compound = '') {
  return TYRE_COLOURS[compound.toUpperCase()] || '#8899aa'
}
