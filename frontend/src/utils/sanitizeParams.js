/**
 * sanitizeParams.js
 *
 * Sanitize and validate URL params (useParams() output) before they
 * are forwarded to the backend as query strings or interpolated into URLs.
 *
 * React Router already percent-decodes params, so we validate the decoded
 * values here rather than doing our own decode.
 */

// Only letters, digits, spaces, hyphens, apostrophes and dots — mirrors
// the backend sanitize_gp_name() allowlist in security.py.
const GP_RE = /^[A-Za-z0-9 \-'.éàü]{1,80}$/

// Year must be a 4-digit integer in the FastF1 range
const YEAR_MIN = 2018
const YEAR_MAX = 2027

// Session types FastF1 supports (matches backend _VALID_SESSION_TYPES)
const VALID_SESSION_TYPES = new Set(['R', 'Q', 'SQ', 'FP1', 'FP2', 'FP3', 'SS'])

/**
 * Validate and sanitize a GP name from a URL param.
 * Returns the cleaned string, or throws a TypeError on invalid input.
 */
export function sanitizeGP(raw) {
  if (!raw || typeof raw !== 'string') throw new TypeError('Missing GP name in URL.')
  const v = decodeURIComponent(raw).trim()
  if (!GP_RE.test(v)) throw new TypeError(`Invalid GP name in URL: "${v}"`)
  return v
}

/**
 * Validate and parse a year from a URL param.
 * Returns an integer, or throws a RangeError on invalid input.
 */
export function sanitizeYear(raw) {
  if (!raw || typeof raw !== 'string') throw new RangeError('Missing year in URL.')
  const n = parseInt(raw, 10)
  if (isNaN(n) || n < YEAR_MIN || n > YEAR_MAX) {
    throw new RangeError(`Year must be ${YEAR_MIN}–${YEAR_MAX}. Got: "${raw}"`)
  }
  return n
}

/**
 * Validate a session type from a query param (defaults to 'R').
 * Returns the canonical uppercase form.
 */
export function sanitizeSessionType(raw, fallback = 'R') {
  if (!raw || typeof raw !== 'string') return fallback
  const v = raw.trim().toUpperCase()
  return VALID_SESSION_TYPES.has(v) ? v : fallback
}

/**
 * Convenience: parse and validate { year, gp } from useParams() output.
 * Returns { year: number, gp: string } or throws.
 */
export function parseRouteParams({ year, gp }) {
  return {
    year: sanitizeYear(year),
    gp: sanitizeGP(gp),
  }
}
