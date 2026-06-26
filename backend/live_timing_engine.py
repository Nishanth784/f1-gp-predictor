"""
live_timing_engine.py — Real-time F1 timing via OpenF1 API.

Polls https://api.openf1.org/v1 every 3 seconds, builds a complete
leaderboard state, and exposes it thread-safely for WebSocket broadcast.

No SignalR, no auth. OpenF1 is ~3-5s behind the broadcast feed.
"""

import threading
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List


OPENF1 = "https://api.openf1.org/v1"
POLL_INTERVAL        = 3    # seconds between fast timing polls
SESSION_CHECK_INTERVAL = 60   # how often to re-query /sessions (rate-limit friendly)
INIT_WINDOW          = 120  # minutes of history to load on cold start


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(endpoint: str, params: dict | None = None) -> List[Dict]:
    try:
        r = requests.get(f"{OPENF1}/{endpoint}", params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[openf1] {endpoint} failed: {e}")
        return []


def _latest_per_driver(rows: List[Dict], key: str = "date") -> Dict[int, Dict]:
    """Keep only the most-recent row per driver_number."""
    out: Dict[int, Dict] = {}
    for row in rows:
        dn = row.get("driver_number")
        if dn is None:
            continue
        prev = out.get(dn)
        if prev is None or row.get(key, "") > prev.get(key, ""):
            out[dn] = row
    return out


def _latest_stint_per_driver(rows: List[Dict]) -> Dict[int, Dict]:
    out: Dict[int, Dict] = {}
    for row in rows:
        dn = row.get("driver_number")
        if dn is None:
            continue
        prev = out.get(dn)
        if prev is None or row.get("stint_number", 0) > prev.get("stint_number", 0):
            out[dn] = row
    return out


def _track_status_from_rc(rc_messages: List[Dict]) -> str:
    """Derive current track status from most recent relevant RC messages."""
    for msg in rc_messages:
        text = (msg.get("message") or "").upper()
        flag = (msg.get("flag") or "").upper()
        if "RED FLAG" in text or flag == "RED":
            return "RedFlag"
        if "SAFETY CAR DEPLOYED" in text or "SAFETY CAR IN" in text:
            return "SafetyCar"
        if "VIRTUAL SAFETY CAR" in text:
            return "VirtualSafetyCar"
        if "SAFETY CAR ENDING" in text or "GREEN" in flag:
            return "AllClear"
    return "AllClear"


def _fmt_gap(val) -> Optional[str]:
    if val is None:
        return None
    try:
        f = float(val)
        return f"+{f:.3f}" if f >= 0 else f"{f:.3f}"
    except (TypeError, ValueError):
        return str(val)  # e.g. "1 LAP"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class LiveTimingEngine:
    def __init__(self):
        self._lock = threading.Lock()

        # Public state snapshot — replaced atomically on every poll
        self._state: Dict[str, Any] = {
            "session":       None,
            "is_live":       False,
            "leaderboard":   [],
            "race_control":  [],
            "weather":       None,
            "lap_count":     {"current": 0, "total": 0},
            "track_status":  "AllClear",
            "last_updated":  None,
        }

        # Internal accumulators — merged on each delta poll
        self._drivers:   Dict[int, Dict] = {}
        self._positions: Dict[int, Dict] = {}   # latest pos per driver
        self._intervals: Dict[int, Dict] = {}   # latest interval per driver
        self._stints:    Dict[int, Dict] = {}   # latest stint per driver
        self._laps:      Dict[int, Dict] = {}   # latest lap per driver
        self._best_laps: Dict[int, Dict] = {}   # session best lap per driver (for practice)
        self._rc:        List[Dict]       = []  # all RC messages this session

        self._radio:     List[Dict]       = []  # team radio clips this session
        self._radio_seen: set             = set()  # dedupe by recording_url

        self._locations:    Dict[int, Dict]        = {}  # latest x/y per driver
        self._loc_history:  Dict[int, List[tuple]] = {}  # per-driver ordered (x,y)

        self._session_key: Optional[int] = None
        self._last_date:   Optional[str] = None  # ISO timestamp of last delta
        self._session_check_ts: float = 0.0     # time.monotonic() of last session check
        self._cached_session = None

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="live-timing")
        self._thread.start()
        print("[live_engine] started")

    def stop(self):
        self._stop.set()
        print("[live_engine] stopped")

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            import copy
            return copy.deepcopy(self._state)

    def is_live(self) -> bool:
        with self._lock:
            return self._state["is_live"]

    # ── Background loop ──────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as e:
                print(f"[live_engine] poll error: {e}")
            self._stop.wait(POLL_INTERVAL)

    def _poll(self):
        # ── 1. Session info — throttled to once per SESSION_CHECK_INTERVAL ──
        now_utc  = datetime.now(timezone.utc)
        mono     = time.monotonic()
        if mono - self._session_check_ts >= SESSION_CHECK_INTERVAL:
            sessions = _get("sessions", {"session_key": "latest"})
            if not sessions:
                return
            self._session_check_ts = mono
            self._cached_session = sessions[0]

        # Use cached session data between checks
        if self._cached_session is None:
            return
        session = self._cached_session

        sk       = session["session_key"]

        # Parse times (OpenF1 uses offset-aware ISO strings)
        def _parse(s):
            return datetime.fromisoformat(s) if s else None

        date_start = _parse(session.get("date_start"))
        date_end   = _parse(session.get("date_end"))

        # Live = between session start and end + 30-min buffer
        is_live = bool(
            date_start and date_end and
            date_start <= now_utc <= date_end + timedelta(minutes=30)
        )

        # ── 1b. If not live, just publish state and return — don't hammer API ──
        if not is_live:
            with self._lock:
                self._state["is_live"]      = False
                self._state["session"]      = {
                    "type":       session.get("session_type", ""),
                    "name":       session.get("session_name", ""),
                    "gp":         session.get("location", ""),
                    "circuit":    session.get("circuit_short_name", ""),
                    "year":       session.get("year"),
                    "date_start": session.get("date_start"),
                    "date_end":   session.get("date_end"),
                }
                self._state["last_updated"] = now_utc.isoformat()
            return

        # ── 2. Session changed → reset accumulators ────────────────────────
        if sk != self._session_key:
            print(f"[live_engine] new session {sk}: {session.get('session_name')} @ {session.get('location')}")
            self._session_key = sk
            self._last_date   = None
            self._drivers     = {}
            self._positions   = {}
            self._intervals   = {}
            self._best_laps   = {}
            self._stints      = {}
            self._laps        = {}
            self._rc          = []
            self._radio       = []
            self._radio_seen  = set()
            self._locations   = {}
            self._loc_history = {}

        # ── 3. Load drivers once per session ──────────────────────────────
        if not self._drivers:
            raw = _get("drivers", {"session_key": sk})
            self._drivers = {d["driver_number"]: d for d in raw}

        # ── 4. Build date filter for delta fetches ─────────────────────────
        if self._last_date is None:
            # Cold start: load last INIT_WINDOW minutes
            since = (now_utc - timedelta(minutes=INIT_WINDOW)).strftime("%Y-%m-%dT%H:%M:%S")
        else:
            since = self._last_date

        date_filter = f"{since}"

        # ── 5. Delta-fetch timing data ─────────────────────────────────────
        def delta(endpoint):
            return _get(endpoint, {"session_key": sk, "date>": date_filter})

        new_pos       = delta("position")
        new_intervals = delta("intervals")
        new_stints    = _get("stints", {"session_key": sk})          # small, always full
        new_laps      = delta("laps")
        new_rc        = delta("race_control")
        new_weather   = _get("weather", {"session_key": sk})
        new_radio     = delta("team_radio")
        new_location  = delta("location")

        # ── 6. Merge into accumulators ─────────────────────────────────────
        for row in new_pos:
            dn = row.get("driver_number")
            if dn and (dn not in self._positions or
                       row.get("date","") > self._positions[dn].get("date","")):
                self._positions[dn] = row

        for row in new_intervals:
            dn = row.get("driver_number")
            if dn and (dn not in self._intervals or
                       row.get("date","") > self._intervals[dn].get("date","")):
                self._intervals[dn] = row

        self._stints = _latest_stint_per_driver(new_stints)

        for row in new_laps:
            dn = row.get("driver_number")
            ln = row.get("lap_number") or 0
            if dn and (dn not in self._laps or
                       ln > (self._laps[dn].get("lap_number") or 0)):
                self._laps[dn] = row

        for msg in new_rc:
            if msg not in self._rc:
                self._rc.append(msg)

        # Keep RC sorted newest-first, cap at 50
        self._rc.sort(key=lambda x: x.get("date",""), reverse=True)
        self._rc = self._rc[:50]

        # Merge team radio — dedupe by recording_url
        for clip in new_radio:
            url = clip.get("recording_url", "")
            if url and url not in self._radio_seen:
                self._radio_seen.add(url)
                dn  = clip.get("driver_number")
                drv = self._drivers.get(dn, {})
                self._radio.append({
                    "date":          clip.get("date"),
                    "driver_number": dn,
                    "acronym":       drv.get("name_acronym", f"#{dn}"),
                    "full_name":     drv.get("full_name", ""),
                    "team":          drv.get("team_name", ""),
                    "team_colour":   "#" + (drv.get("team_colour") or "888888"),
                    "recording_url": url,
                })
        # Newest first, keep last 30
        self._radio.sort(key=lambda x: x.get("date",""), reverse=True)
        self._radio = self._radio[:30]
        # Merge GPS locations — latest per driver + per-driver ordered history
        for row in sorted(new_location, key=lambda r: r.get("date", "")):
            dn = row.get("driver_number")
            x, y = row.get("x"), row.get("y")
            if dn is None or x is None or y is None:
                continue
            if (dn not in self._locations or
                    row.get("date", "") > self._locations[dn].get("date", "")):
                self._locations[dn] = row
            if dn not in self._loc_history:
                self._loc_history[dn] = []
            self._loc_history[dn].append((float(x), float(y)))
            # Cap per driver at 2 500 points (~1-2 full laps)
            if len(self._loc_history[dn]) > 2500:
                self._loc_history[dn] = self._loc_history[dn][-2500:]

        # Build car_positions for output
        car_positions = []
        for dn, loc in self._locations.items():
            drv = self._drivers.get(dn, {})
            x, y = loc.get("x"), loc.get("y")
            if x is not None and y is not None:
                car_positions.append({
                    "driver_number": dn,
                    "acronym":       drv.get("name_acronym", f"#{dn}"),
                    "team_colour":   "#" + (drv.get("team_colour") or "888888"),
                    "x":             float(x),
                    "y":             float(y),
                })

        # Build track_outline: use the car with the most GPS history (cleanest lap trace)
        track_outline: List[Dict] = []
        if self._loc_history:
            best_dn   = max(self._loc_history, key=lambda k: len(self._loc_history[k]))
            best_path = self._loc_history[best_dn]
            step      = max(1, len(best_path) // 600)
            track_outline = [{"x": p[0], "y": p[1]} for p in best_path[::step]]

        # Latest weather snapshot
        weather = new_weather[-1] if new_weather else None

        # ── 7. Build leaderboard ───────────────────────────────────────────
        leaderboard = []
        total_laps  = max((v.get("lap_number") or 0 for v in self._laps.values()), default=0)

        for dn, drv in self._drivers.items():
            pos_row  = self._positions.get(dn)
            iv_row   = self._intervals.get(dn)
            st_row   = self._stints.get(dn)
            lap_row  = self._laps.get(dn)

            position = (pos_row or {}).get("position") or 99

            # Gap
            gap_to_leader = _fmt_gap((iv_row or {}).get("gap_to_leader"))
            gap_to_next   = _fmt_gap((iv_row or {}).get("interval"))

            # Tyre
            compound = (st_row or {}).get("compound", "UNKNOWN")
            tyre_age = 0
            if st_row and lap_row:
                cur_lap   = lap_row.get("lap_number") or 0
                lap_start = st_row.get("lap_start") or cur_lap
                age_start = st_row.get("tyre_age_at_start") or 0
                tyre_age  = age_start + max(0, cur_lap - lap_start)

            # Lap duration → format mm:ss.mmm
            last_lap_s = (lap_row or {}).get("lap_duration")
            last_lap_fmt = None
            if last_lap_s is not None:
                try:
                    secs = float(last_lap_s)
                    mins = int(secs // 60)
                    last_lap_fmt = f"{mins}:{secs % 60:06.3f}"
                except (TypeError, ValueError):
                    pass

            # Best lap for practice leaderboard
            best_row = self._best_laps.get(dn, {})
            best_lap_s = None
            best_lap_fmt = None
            if best_row.get("lap_duration"):
                try:
                    best_lap_s = float(best_row["lap_duration"])
                    mins = int(best_lap_s // 60)
                    best_lap_fmt = f"{mins}:{best_lap_s % 60:06.3f}"
                except (TypeError, ValueError):
                    pass

            leaderboard.append({
                "position":      position,
                "driver_number": dn,
                "acronym":       drv.get("name_acronym", ""),
                "full_name":     drv.get("full_name", ""),
                "team":          drv.get("team_name", ""),
                "team_colour":   "#" + (drv.get("team_colour") or "888888"),
                "gap_to_leader": gap_to_leader,
                "gap_to_next":   gap_to_next,
                "compound":      compound,
                "tyre_age":      tyre_age,
                "current_lap":   (lap_row or {}).get("lap_number") or 0,
                "last_lap_fmt":  last_lap_fmt,
                "best_lap_s":    best_lap_s,
                "best_lap_fmt":  best_lap_fmt,
                "is_pit_out":    bool((lap_row or {}).get("is_pit_out_lap", False)),
            })

        leaderboard.sort(key=lambda x: x["position"])

        # ── 8. Track status ────────────────────────────────────────────────
        track_status = _track_status_from_rc(self._rc[:10])

        # ── 9. Format RC for output ────────────────────────────────────────
        rc_out = []
        for msg in self._rc[:20]:
            rc_out.append({
                "date":     msg.get("date"),
                "category": msg.get("category", ""),
                "message":  msg.get("message", ""),
                "flag":     msg.get("flag", ""),
                "lap":      msg.get("lap_number"),
                "driver":   msg.get("driver_number"),
                "scope":    msg.get("scope", ""),
            })

        # ── 10. Format weather ─────────────────────────────────────────────
        wx_out = None
        if weather:
            wx_out = {
                "air_temp":   weather.get("air_temperature"),
                "track_temp": weather.get("track_temperature"),
                "humidity":   weather.get("humidity"),
                "wind_speed": weather.get("wind_speed"),
                "rainfall":   bool(weather.get("rainfall", False)),
            }

        # ── 11. Advance delta timestamp ────────────────────────────────────
        self._last_date = now_utc.strftime("%Y-%m-%dT%H:%M:%S")

        # ── 12. Publish state ──────────────────────────────────────────────
        new_state = {
            "session": {
                "key":        sk,
                "type":       session.get("session_type", ""),
                "name":       session.get("session_name", ""),
                "gp":         session.get("location", ""),
                "circuit":    session.get("circuit_short_name", ""),
                "year":       session.get("year"),
                "date_start": session.get("date_start"),
                "date_end":   session.get("date_end"),
            },
            "is_live":       is_live,
            "leaderboard":   leaderboard,
            "race_control":  rc_out,
            "team_radio":    self._radio[:30],
            "car_positions": car_positions,
            "track_outline": track_outline,
            "weather":       wx_out,
            "lap_count":     {"current": total_laps, "total": 0},
            "track_status":  track_status,
            "last_updated":  now_utc.isoformat(),
        }

        with self._lock:
            self._state = new_state

        if is_live:
            print(f"[live_engine] {session.get('session_name')} | "
                  f"lap {total_laps} | {track_status} | "
                  f"{len(leaderboard)} drivers | rc={len(self._rc)} | "
                  f"cars_gps={len(car_positions)}")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine = LiveTimingEngine()


def get_engine() -> LiveTimingEngine:
    return _engine


def start_engine():
    _engine.start()


def get_live_state() -> Dict[str, Any]:
    return _engine.get_state()


def is_session_live() -> bool:
    return _engine.is_live()
