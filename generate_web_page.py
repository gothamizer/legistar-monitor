#!/usr/bin/env python3
"""Generate the static hearing-monitor web page.

Reads ``data/processed_events_for_web.json`` (produced by check_new_hearings.py)
and writes a single self-contained ``docs/index.html``.

The data contract is unchanged from the monitor:
  - upcoming_hearings:       [ entry, ... ]          (entry has event_data + user_facing_tags)
  - updates_since_last_run:  [ {type, alert_timestamp, data: entry}, ... ]
  - updates_last_7_days:     [ ... same shape ... ]
  - updates_last_30_days:    [ ... same shape ... ]
  - cancellation_notices:    [ entry, ... ]          (optional)
  - generation_timestamp:    ISO string

The page renders entirely client-side from a JSON blob embedded in the HTML, so
filtering, search, and the updates rail are instant with no server round-trips.

Design: a calm civic timetable. The schedule and the recent-changes rail are
both visible at once (no tabs hiding one behind the other). Rows, not cards;
tabular alignment; a monospace voice for times/dates/metadata.
"""
import os
import json
import logging
from datetime import datetime
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_page_generator')

DATA_DIR = "data"
PROCESSED_EVENTS_FILE = os.path.join(DATA_DIR, "processed_events_for_web.json")
WEB_DIR = "docs"
INDEX_HTML = os.path.join(WEB_DIR, "index.html")


# --------------------------------------------------------------------------- #
# Data shaping: flatten the monitor's structures into a compact client model.
# Keeping all date/label logic in JS keeps the two views (list + updates)
# perfectly consistent and avoids server/client formatting drift.
# --------------------------------------------------------------------------- #

def _event_fields(event_data):
    """Pull the small set of fields the UI actually shows from a raw event."""
    return {
        "id": event_data.get("EventId"),
        "committee": event_data.get("EventBodyName") or "",
        "topic": event_data.get("SyntheticMeetingTopic") or "",
        "date": event_data.get("EventDate") or "",
        "time": event_data.get("EventTime") or "",
        "location": event_data.get("EventLocation") or "",
        "comment": event_data.get("EventComment") or "",
        "agenda": event_data.get("EventAgendaFile") or "",
        "detail": event_data.get("EventInSiteURL") or "",
    }


def _hearing_model(entry):
    """A single upcoming hearing (or cancellation notice) for the list view."""
    event_data = entry.get("event_data", {})
    model = _event_fields(event_data)
    tags = entry.get("user_facing_tags", []) or []
    model["status"] = entry.get("current_status") or "active"

    flags = []
    if "new_hearing_tag" in tags:
        flags.append("new")
    if "rescheduled_hearing_tag" in tags:
        flags.append("rescheduled")
    if "deferred_hearing_tag" in tags:
        flags.append("deferred")
    if "cancelled_hearing_tag" in tags:
        flags.append("cancelled")
    model["flags"] = flags

    orig = entry.get("original_event_details_if_rescheduled")
    if orig:
        model["rescheduled_from"] = {
            "date": orig.get("original_date") or "",
            "time": orig.get("original_time") or "",
        }
    return model


def _update_model(item):
    """A single line in the Updates rail."""
    entry = item.get("data", {})
    event_data = entry.get("event_data", {})
    model = _event_fields(event_data)
    model["type"] = item.get("type") or "new"
    model["alert"] = item.get("alert_timestamp") or ""

    orig = entry.get("original_event_details_if_rescheduled")
    if orig:
        model["rescheduled_from"] = {
            "date": orig.get("original_date") or "",
            "time": orig.get("original_time") or "",
        }
    resched = entry.get("rescheduled_event_details_if_deferred")
    if resched:
        model["rescheduled_to"] = {
            "date": resched.get("new_date") or "",
            "time": resched.get("new_time") or "",
        }
    return model


def build_client_data(processed_data):
    """Transform the monitor's processed data into the compact client payload."""
    hearings = [_hearing_model(e) for e in processed_data.get("upcoming_hearings", [])]
    cancellations = [_hearing_model(e) for e in processed_data.get("cancellation_notices", [])]

    return {
        "generated": processed_data.get("generation_timestamp") or datetime.now().isoformat(),
        "hearings": hearings,
        "cancellations": cancellations,
        "updates": {
            "since_last_run": [_update_model(i) for i in processed_data.get("updates_since_last_run", [])],
            "last_7_days": [_update_model(i) for i in processed_data.get("updates_last_7_days", [])],
            "last_30_days": [_update_model(i) for i in processed_data.get("updates_last_30_days", [])],
        },
    }


# --------------------------------------------------------------------------- #
# Presentation. CSS/JS are static; only the data blob and title vary.
# --------------------------------------------------------------------------- #

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Libre+Franklin:wght@400;500;600;700&'
    'family=Spline+Sans+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

PAGE_CSS = """
:root {
  /* Civic paper palette — warm off-white, ink, one municipal blue. */
  --paper: #f4f1ea;
  --paper-2: #efebe2;
  --surface: #fbf9f4;
  --ink: #1b1a17;
  --ink-2: #46443d;
  --ink-3: #6f6c62;
  --ink-4: #97948a;
  --rule: #d9d4c7;
  --rule-2: #c8c2b2;
  --gov: #1d3f73;          /* municipal blue */
  --gov-soft: #e4e9f1;
  --gov-ink: #16335e;
  --new: #1f6b43;  --new-bg: #e2efe6;
  --resched: #8a5a14; --resched-bg: #f3e9d4;
  --defer: #9a4d12; --defer-bg: #f4e3d4;
  --cancel: #9c2a23; --cancel-bg: #f3e0dd;
  --sans: 'Libre Franklin', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono: 'Spline Sans Mono', ui-monospace, 'SF Mono', Menlo, monospace;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; color: var(--ink); background: var(--paper);
  font-family: var(--sans); font-size: 15px; line-height: 1.5;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
a { color: var(--gov); text-decoration: none; }
a:hover { text-decoration: underline; }

.kicker {
  font-family: var(--mono); font-size: 11px; font-weight: 500;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink-4);
}

/* Masthead -------------------------------------------------------------- */
.masthead { border-bottom: 2px solid var(--ink); background: var(--paper); }
.masthead-inner { max-width: 1180px; margin: 0 auto; padding: 22px 28px 18px; }
.brand { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.brand-left { display: flex; flex-direction: column; gap: 5px; }
.brand .kicker {
  font-family: var(--sans); font-size: 11.5px; font-weight: 600;
  letter-spacing: .13em; text-transform: uppercase; color: var(--gov);
}
.brand h1 {
  margin: 0; font-size: 27px; font-weight: 700; letter-spacing: -.02em; color: var(--ink);
  line-height: 1.05;
}
.brand .sub { font-size: 13px; color: var(--ink-3); letter-spacing: 0; }
.stamp { text-align: right; }
.stamp .stamp-k { font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-4); }
.stamp .stamp-v { font-family: var(--mono); font-size: 13px; color: var(--ink-2); margin-top: 2px; white-space: nowrap; }

/* Toolbar --------------------------------------------------------------- */
.toolbar {
  position: sticky; top: 0; z-index: 40;
  background: var(--paper); border-bottom: 1px solid var(--rule-2);
}
.toolbar-inner {
  max-width: 1180px; margin: 0 auto; padding: 12px 28px;
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
}
.search { position: relative; flex: 1 1 320px; min-width: 200px; }
.search input {
  width: 100%; padding: 10px 12px 10px 36px; font-size: 14px; font-family: var(--sans);
  color: var(--ink); background: var(--surface);
  border: 1px solid var(--rule-2); border-radius: 2px; outline: none;
}
.search input::placeholder { color: var(--ink-4); }
.search input:focus { border-color: var(--gov); box-shadow: inset 0 0 0 1px var(--gov); }
.search svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--ink-4); }
select.committee {
  padding: 10px 34px 10px 12px; font-size: 14px; font-family: var(--sans);
  color: var(--ink); background: var(--surface); cursor: pointer;
  border: 1px solid var(--rule-2); border-radius: 2px; appearance: none; max-width: 300px;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'><path d='M3 4.5L6 7.5L9 4.5' stroke='%236f6c62' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
  background-repeat: no-repeat; background-position: right 12px center;
}
select.committee:focus { border-color: var(--gov); outline: none; box-shadow: inset 0 0 0 1px var(--gov); }
.tool-count { font-family: var(--mono); font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.tool-count b { color: var(--ink); font-weight: 600; }

/* Workspace: schedule + updates rail, both visible --------------------- */
.workspace {
  max-width: 1180px; margin: 0 auto; padding: 0 28px 72px;
  display: grid; grid-template-columns: 332px minmax(0, 1fr); gap: 0;
}
.rail {
  grid-column: 1; grid-row: 1;
  border-right: 1px solid var(--rule-2); padding: 4px 28px 0 0;
  align-self: start; position: sticky; top: 61px;
  max-height: calc(100vh - 61px); overflow-y: auto;
}
.schedule { grid-column: 2; grid-row: 1; padding: 4px 0 0 36px; min-width: 0; }

/* Section headers ------------------------------------------------------- */
.sec-head { display: flex; align-items: baseline; gap: 10px; padding: 22px 0 8px; }
.sec-head h2 { margin: 0; font-size: 14px; font-weight: 700; letter-spacing: .01em; color: var(--ink); }
.sec-head .n { font-family: var(--mono); font-size: 12px; color: var(--ink-3); }
.sec-head .rule { flex: 1; }

/* Day groups ------------------------------------------------------------ */
.daygroup { margin-top: 26px; }
.daygroup:first-of-type { margin-top: 8px; }
.dayhead {
  position: sticky; top: 61px; z-index: 10;
  display: flex; align-items: baseline; gap: 12px;
  padding: 8px 0 7px; background: var(--paper);
  border-bottom: 2px solid var(--ink);
}
.dayhead .d-rel { font-size: 13px; font-weight: 700; letter-spacing: .01em; color: var(--ink); }
.dayhead .d-abs { font-family: var(--mono); font-size: 12px; color: var(--ink-3); letter-spacing: .02em; }
.dayhead .d-fill { flex: 1; }
.dayhead .d-n { font-family: var(--mono); font-size: 11.5px; color: var(--ink-4); }
.dayhead.is-today .d-rel { color: var(--gov); }
.dayhead.is-today { border-bottom-color: var(--gov); }
.dayhead.is-cancel .d-rel { color: var(--cancel); }
.dayhead.is-cancel { border-bottom-color: var(--cancel); }

/* Hearing rows ---------------------------------------------------------- */
.row {
  display: grid; grid-template-columns: 78px minmax(0,1fr) auto;
  gap: 4px 18px; align-items: baseline;
  padding: 12px 4px; border-bottom: 1px solid var(--rule);
}
.row:hover { background: var(--surface); }
.row .when {
  grid-row: 1 / span 3; font-family: var(--mono); font-size: 13px; font-weight: 500;
  color: var(--ink); white-space: nowrap; padding-top: 1px;
}
.row .when.tbd { color: var(--ink-4); }
.row .committee {
  grid-column: 2; font-size: 15px; font-weight: 600; color: var(--ink); line-height: 1.3;
}
.row .topic { grid-column: 2; font-size: 13px; color: var(--ink-2); margin-top: 2px; }
.row .meta {
  grid-column: 2; font-family: var(--mono); font-size: 11.5px; color: var(--ink-3);
  margin-top: 5px; display: flex; flex-wrap: wrap; gap: 2px 16px; letter-spacing: .01em;
}
.row .meta .loc { display: inline-flex; align-items: center; gap: 5px; }
.row .meta svg { color: var(--ink-4); flex-shrink: 0; }
.row .meta .change { color: var(--resched); }
.row .actions {
  grid-column: 3; grid-row: 1 / span 3; display: flex; flex-direction: column;
  align-items: flex-end; gap: 7px; white-space: nowrap; padding-top: 2px;
}
.act {
  appearance: none; border: 0; background: transparent; padding: 0; cursor: pointer;
  font-family: var(--mono); font-size: 11.5px; font-weight: 500; letter-spacing: .02em;
  color: var(--gov); display: inline-flex; align-items: center; gap: 5px;
}
.act:hover { text-decoration: underline; }
.act svg { color: var(--gov); opacity: .8; }

/* Status flags ---------------------------------------------------------- */
.flags { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: middle; }
.flag {
  font-family: var(--mono); font-size: 9.5px; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; padding: 2px 6px; border-radius: 2px; line-height: 1.4;
  position: relative; top: -1px;
}
.flag.new { color: var(--new); background: var(--new-bg); }
.flag.rescheduled { color: var(--resched); background: var(--resched-bg); }
.flag.deferred { color: var(--defer); background: var(--defer-bg); }
.flag.cancelled { color: var(--cancel); background: var(--cancel-bg); }

/* Updates rail ---------------------------------------------------------- */
.rail-head { display: flex; align-items: baseline; justify-content: space-between; padding: 4px 0 0; }
.rail-head h2 { margin: 0; font-size: 14px; font-weight: 700; color: var(--ink); }
.win { display: flex; gap: 0; margin: 12px 0 4px; border: 1px solid var(--rule-2); border-radius: 2px; overflow: hidden; }
.win button {
  flex: 1; appearance: none; border: 0; background: var(--surface); cursor: pointer;
  font-family: var(--mono); font-size: 11px; font-weight: 500; letter-spacing: .03em;
  color: var(--ink-3); padding: 7px 4px; border-right: 1px solid var(--rule-2);
}
.win button:last-child { border-right: 0; }
.win button[aria-selected="true"] { background: var(--gov); color: #fff; }
.urow { padding: 13px 0; border-bottom: 1px solid var(--rule); }
.urow:last-child { border-bottom: 0; }
.urow .utop { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 5px; }
.urow .uwhen { font-family: var(--mono); font-size: 10.5px; color: var(--ink-4); white-space: nowrap; letter-spacing: .02em; }
.urow .ucommittee { font-size: 13.5px; font-weight: 600; color: var(--ink); line-height: 1.3; }
.urow .utopic { font-size: 12px; color: var(--ink-2); margin-top: 2px; }
.urow .uline { font-family: var(--mono); font-size: 11.5px; color: var(--ink-3); margin-top: 5px; line-height: 1.5; }
.urow .uline del { color: var(--cancel); text-decoration-thickness: 1px; }
.urow .uline strong { color: var(--ink); font-weight: 600; }
.urow .uact { margin-top: 7px; }

/* Empty + footer -------------------------------------------------------- */
.empty { color: var(--ink-4); padding: 40px 6px; font-size: 13.5px; text-align: center; }
.empty.big { padding: 72px 20px; }
.empty .e-mark { font-family: var(--mono); font-size: 22px; color: var(--rule-2); display: block; margin-bottom: 8px; }
.foot {
  border-top: 1px solid var(--rule-2);
  max-width: 1180px; margin: 0 auto; padding: 20px 28px 48px;
  font-family: var(--mono); font-size: 11px; color: var(--ink-4); letter-spacing: .02em;
  line-height: 1.7;
}
.foot a { color: var(--ink-3); text-decoration: underline; }

/* Responsive ------------------------------------------------------------ */
@media (max-width: 880px) {
  .workspace { grid-template-columns: 1fr; padding: 0 18px 64px; }
  .schedule { grid-column: 1; grid-row: auto; padding: 0; order: 2; }
  .rail {
    grid-column: 1; grid-row: auto;
    position: static; border-right: 0; padding: 0; max-height: none;
    border-bottom: 1px solid var(--rule-2); margin-bottom: 8px; order: 1;
    padding-bottom: 16px;
  }
  .masthead-inner, .toolbar-inner { padding-left: 18px; padding-right: 18px; }
}
@media (max-width: 540px) {
  .brand h1 { font-size: 22px; }
  .row { grid-template-columns: 64px minmax(0,1fr); }
  .row .when { grid-row: 1 / span 4; }
  .row .actions { grid-column: 2; grid-row: auto; flex-direction: row; align-items: center; gap: 16px; margin-top: 6px; }
  .stamp { text-align: left; }
}
"""


def _page_js(default_window):
    """Client behaviour. Reads window.__DATA__ and renders the workspace."""
    return """
const DATA = window.__DATA__;
const DEFAULT_WINDOW = %s;

// ---- date helpers (all client-side for consistency) ----------------------
const WD = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const WDS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const MO = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const MOS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function parseDate(s) {
  if (!s) return null;
  const m = String(s).match(/^(\\d{4})-(\\d{2})-(\\d{2})/);
  if (!m) { const d = new Date(s); return isNaN(d) ? null : d; }
  return new Date(+m[1], +m[2]-1, +m[3]);
}
function parseTime(s) {
  if (!s) return null;
  let m = String(s).match(/^(\\d{1,2}):(\\d{2})\\s*([AaPp][Mm])$/);
  if (m) { let h=+m[1]%%12; if (/[Pp]/.test(m[3])) h+=12; return [h, +m[2]]; }
  m = String(s).match(/^(\\d{1,2}):(\\d{2})/);
  if (m) return [+m[1], +m[2]];
  return null;
}
function fmtTime(s) {
  const t = parseTime(s);
  if (!t) return s || 'TBD';
  let [h,mi] = t; const ap = h>=12 ? 'pm':'am'; let hh = h%%12; if (hh===0) hh=12;
  return hh + ':' + String(mi).padStart(2,'0') + ap;
}
function dayKey(d) { return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function startOfToday() { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
function relDay(d) {
  const diff = Math.round((d - startOfToday()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Tomorrow';
  return WD[d.getDay()];
}
function absDay(d) { return WDS[d.getDay()] + ' ' + MOS[d.getMonth()] + ' ' + d.getDate(); }
function absDayLong(d) { return MO[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear(); }
function fmtAlert(s) {
  const d = new Date(s); if (isNaN(d)) return '';
  const diff = Math.floor((new Date() - d)/1000);
  if (diff < 3600) { const m = Math.max(1, Math.floor(diff/60)); return m + 'm ago'; }
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  const days = Math.floor(diff/86400);
  if (days < 30) return days + 'd ago';
  return MOS[d.getMonth()] + ' ' + d.getDate();
}
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

const ICON = {
  search: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M11 11l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  loc: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 1.5c-2.5 0-4.5 2-4.5 4.5 0 3.2 4.5 8 4.5 8s4.5-4.8 4.5-8c0-2.5-2-4.5-4.5-4.5z" stroke="currentColor" stroke-width="1.3"/><circle cx="8" cy="6" r="1.5" stroke="currentColor" stroke-width="1.3"/></svg>',
  cal: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="2.5" y="3.5" width="11" height="10" rx="1" stroke="currentColor" stroke-width="1.3"/><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  ext: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M6 3.5H4A1.5 1.5 0 002.5 5v7A1.5 1.5 0 004 13.5h7a1.5 1.5 0 001.5-1.5v-2M9.5 2.5h4v4M13 3l-5.5 5.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

// ---- iCalendar download --------------------------------------------------
function pad(n){ return String(n).padStart(2,'0'); }
function icalStamp(d){ return d.getUTCFullYear()+pad(d.getUTCMonth()+1)+pad(d.getUTCDate())+'T'+pad(d.getUTCHours())+pad(d.getUTCMinutes())+pad(d.getUTCSeconds())+'Z'; }
function escICal(s){ return String(s||'').replace(/\\\\/g,'\\\\\\\\').replace(/;/g,'\\\\;').replace(/,/g,'\\\\,').replace(/\\n/g,'\\\\n'); }
function downloadICS(ev) {
  const d = parseDate(ev.date); const t = parseTime(ev.time) || [9,0];
  if (!d) return;
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate(), t[0], t[1]);
  const end = new Date(start.getTime() + 60*60000);
  const summary = ev.committee + (ev.topic ? ': ' + ev.topic : '');
  let desc = ev.topic || '';
  if (ev.comment) desc += (desc?'\\n\\n':'') + ev.comment;
  if (ev.detail) desc += (desc?'\\n\\n':'') + ev.detail;
  const uid = 'hearing-' + (ev.id||'x') + '-' + icalStamp(start) + '@nyc-hearings';
  const lines = [
    'BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//NYC Hearing Monitor//EN','METHOD:PUBLISH',
    'BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+icalStamp(new Date()),
    'DTSTART:'+icalStamp(start),'DTEND:'+icalStamp(end),
    'SUMMARY:'+escICal(summary),'DESCRIPTION:'+escICal(desc),'LOCATION:'+escICal(ev.location),
    'END:VEVENT','END:VCALENDAR'
  ];
  const blob = new Blob([lines.join('\\r\\n')], {type:'text/calendar;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const slug = (ev.committee||'hearing').replace(/[^a-z0-9]+/gi,'-').toLowerCase().replace(/^-|-$/g,'');
  a.href = url; a.download = slug + '-' + (ev.date||'').slice(0,10) + '.ics';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url), 1000);
}

// ---- schedule rows -------------------------------------------------------
function flagsHTML(flags) {
  if (!flags || !flags.length) return '';
  return '<span class="flags">' + flags.map(f => '<span class="flag '+f+'">'+f+'</span>').join('') + '</span>';
}
function actionsHTML(ev) {
  let h = '';
  if (ev.date && ev.status === 'active') h += '<button class="act js-cal" type="button">'+ICON.cal+'Calendar</button>';
  if (ev.agenda) h += '<a class="act" target="_blank" rel="noopener" href="'+esc(ev.agenda)+'">'+ICON.ext+'Agenda</a>';
  else if (ev.detail) h += '<a class="act" target="_blank" rel="noopener" href="'+esc(ev.detail)+'">'+ICON.ext+'Details</a>';
  return h;
}
function hearingRow(ev) {
  const tbd = !parseTime(ev.time);
  let meta = [];
  if (ev.location) meta.push('<span class="loc">'+ICON.loc+esc(ev.location)+'</span>');
  if (ev.comment) meta.push('<span>'+esc(ev.comment)+'</span>');
  if (ev.rescheduled_from && ev.rescheduled_from.date) {
    const od = parseDate(ev.rescheduled_from.date);
    meta.push('<span class="change">moved from ' + (od ? absDay(od) : esc(ev.rescheduled_from.date)) + '</span>');
  }
  const r = document.createElement('div');
  r.className = 'row';
  r.innerHTML =
    '<div class="when'+(tbd?' tbd':'')+'">'+esc(fmtTime(ev.time))+'</div>' +
    '<div class="committee">'+esc(ev.committee)+flagsHTML(ev.flags)+'</div>' +
    (ev.topic ? '<div class="topic">'+esc(ev.topic)+'</div>' : '') +
    (meta.length ? '<div class="meta">'+meta.join('')+'</div>' : '') +
    '<div class="actions">'+actionsHTML(ev)+'</div>';
  const cal = r.querySelector('.js-cal');
  if (cal) cal.addEventListener('click', () => downloadICS(ev));
  return r;
}

// ---- elements ------------------------------------------------------------
const els = {
  schedule: document.getElementById('schedule'),
  rail: document.getElementById('rail-list'),
  search: document.getElementById('q'),
  committee: document.getElementById('committee'),
  count: document.getElementById('result-count'),
};

function populateCommittees() {
  const names = Array.from(new Set(DATA.hearings.map(h => h.committee).filter(Boolean))).sort();
  for (const n of names) {
    const o = document.createElement('option'); o.value = n; o.textContent = n;
    els.committee.appendChild(o);
  }
}

function dayGroup(relText, absText, n, cls) {
  const head = document.createElement('div');
  head.className = 'dayhead' + (cls ? ' ' + cls : '');
  head.innerHTML =
    '<span class="d-rel">'+esc(relText)+'</span>' +
    (absText ? '<span class="d-abs">'+esc(absText)+'</span>' : '') +
    '<span class="d-fill"></span>' +
    '<span class="d-n">'+n+'</span>';
  const grp = document.createElement('div');
  grp.className = 'daygroup';
  grp.appendChild(head);
  return grp;
}

function renderSchedule() {
  const q = els.search.value.trim().toLowerCase();
  const com = els.committee.value;
  const filtered = !q && !com;
  const list = DATA.hearings.filter(h => {
    if (com && h.committee !== com) return false;
    if (q && !(h.committee+' '+h.topic+' '+h.location).toLowerCase().includes(q)) return false;
    return true;
  });

  els.schedule.innerHTML = '';
  els.count.innerHTML = '<b>'+list.length+'</b> '+(list.length===1?'hearing':'hearings');

  // Cancellation notices surface first, only in the unfiltered view.
  if (filtered && DATA.cancellations && DATA.cancellations.length) {
    const grp = dayGroup('Cancelled', '', DATA.cancellations.length, 'is-cancel');
    DATA.cancellations.forEach(ev => grp.appendChild(hearingRow(ev)));
    els.schedule.appendChild(grp);
  }

  if (!list.length) {
    const e = document.createElement('div');
    e.className = 'empty big';
    e.innerHTML = '<span class="e-mark">[  ]</span>' + (filtered ? 'No upcoming hearings on file.' : 'No hearings match this filter.');
    els.schedule.appendChild(e);
    return;
  }

  const groups = new Map();
  for (const h of list) {
    const d = parseDate(h.date);
    const k = d ? dayKey(d) : 'tbd';
    if (!groups.has(k)) groups.set(k, { d, items: [] });
    groups.get(k).items.push(h);
  }
  const todayKey = dayKey(startOfToday());
  for (const [k, g] of groups) {
    const isToday = k === todayKey;
    const rel = g.d ? relDay(g.d) : 'Date pending';
    const abs = g.d ? absDayLong(g.d) : '';
    const grp = dayGroup(rel, abs, g.items.length, isToday ? 'is-today' : '');
    g.items.sort((a,b) => {
      const ta = parseTime(a.time), tb = parseTime(b.time);
      if (!ta && !tb) return 0; if (!ta) return 1; if (!tb) return -1;
      return (ta[0]-tb[0]) || (ta[1]-tb[1]);
    });
    g.items.forEach(ev => grp.appendChild(hearingRow(ev)));
    els.schedule.appendChild(grp);
  }
}

// ---- updates rail --------------------------------------------------------
let currentWindow = DEFAULT_WINDOW;

function updateRow(u) {
  const el = document.createElement('div');
  el.className = 'urow';
  const label = u.type === 'new' ? 'New' : u.type === 'deferred' ? 'Deferred' : 'Cancelled';
  let line = '';
  if (u.type === 'new') {
    const d = parseDate(u.date);
    line = (d ? absDay(d) : 'Date TBD') + (parseTime(u.time) ? ' · ' + fmtTime(u.time) : '');
    if (u.rescheduled_from && u.rescheduled_from.date) {
      const od = parseDate(u.rescheduled_from.date);
      line += '<br>moved from ' + (od ? absDay(od) : '');
    }
  } else if (u.type === 'deferred') {
    const d = parseDate(u.date);
    line = 'was <del>' + (d ? absDay(d) : esc(u.date)) + (parseTime(u.time) ? ' ' + fmtTime(u.time) : '') + '</del>';
    if (u.rescheduled_to && u.rescheduled_to.date) {
      const nd = parseDate(u.rescheduled_to.date);
      line += '<br><strong>now ' + (nd ? absDay(nd) : '') + (parseTime(u.rescheduled_to.time) ? ' ' + fmtTime(u.rescheduled_to.time) : '') + '</strong>';
    } else {
      line += '<br>new date pending';
    }
  } else if (u.type === 'cancelled') {
    const d = parseDate(u.date);
    line = 'was <del>' + (d ? absDay(d) : esc(u.date)) + '</del>';
  }
  el.innerHTML =
    '<div class="utop"><span class="flag '+u.type+'">'+label+'</span><span class="uwhen">'+esc(fmtAlert(u.alert))+'</span></div>' +
    '<div class="ucommittee">'+esc(u.committee)+'</div>' +
    (u.topic ? '<div class="utopic">'+esc(u.topic)+'</div>' : '') +
    '<div class="uline">'+line+'</div>' +
    ((u.agenda||u.detail) ? '<div class="uact"><a class="act" target="_blank" rel="noopener" href="'+esc(u.agenda||u.detail)+'">'+ICON.ext+(u.agenda?'Agenda':'Details')+'</a></div>' : '');
  return el;
}

function renderUpdates() {
  const items = DATA.updates[currentWindow] || [];
  els.rail.innerHTML = '';
  if (!items.length) {
    const e = document.createElement('div');
    e.className = 'empty';
    e.innerHTML = '<span class="e-mark">—</span>No changes in this period.';
    els.rail.appendChild(e);
    return;
  }
  items.forEach(u => els.rail.appendChild(updateRow(u)));
}

function buildWindowToggle() {
  const win = document.getElementById('win');
  const opts = [['since_last_run','Latest'],['last_7_days','7 days'],['last_30_days','30 days']];
  win.innerHTML = '';
  for (const [val,label] of opts) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label + ' · ' + (DATA.updates[val]||[]).length;
    b.setAttribute('aria-selected', String(val === currentWindow));
    b.addEventListener('click', () => {
      currentWindow = val;
      win.querySelectorAll('button').forEach(x => x.setAttribute('aria-selected','false'));
      b.setAttribute('aria-selected','true');
      renderUpdates();
    });
    win.appendChild(b);
  }
}

// ---- init ----------------------------------------------------------------
function init() {
  populateCommittees();
  buildWindowToggle();
  renderSchedule();
  renderUpdates();
  els.search.addEventListener('input', renderSchedule);
  els.committee.addEventListener('change', renderSchedule);
}
init();
""" % json.dumps(default_window)


def generate_html_page_content(processed_data, page_title="NYC Council Hearings",
                               updates_filter_value="since_last_run"):
    """Assemble the full HTML document."""
    client_data = build_client_data(processed_data)
    data_json = json.dumps(client_data, separators=(',', ':'))

    win_map = {"since_last_run": "since_last_run", "last_7_days": "last_7_days", "last_30_days": "last_30_days"}
    default_window = win_map.get(updates_filter_value, "since_last_run")

    try:
        gen_dt = datetime.fromisoformat(client_data["generated"])
        updated_display = gen_dt.strftime("%b %-d, %Y · %-I:%M %p")
    except (ValueError, TypeError):
        updated_display = client_data["generated"]

    search_icon = ('<svg width="16" height="16" viewBox="0 0 16 16" fill="none">'
                   '<circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.5"/>'
                   '<path d="M11 11l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>')

    js = _page_js(default_window)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<meta name="description" content="Upcoming New York City Council committee hearings and recent schedule changes.">
{FONT_LINKS}
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="masthead">
  <div class="masthead-inner">
    <div class="brand">
      <div class="brand-left">
        <span class="kicker">New York City Council</span>
        <h1>{page_title}</h1>
        <span class="sub">Committee hearing schedule &amp; recent changes</span>
      </div>
      <div class="stamp">
        <div class="stamp-k">Last checked</div>
        <div class="stamp-v">{updated_display}</div>
      </div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-inner">
    <label class="search">
      {search_icon}
      <input id="q" type="search" placeholder="Search committee, topic, or location" autocomplete="off" aria-label="Search hearings">
    </label>
    <select id="committee" class="committee" aria-label="Filter by committee">
      <option value="">All committees</option>
    </select>
    <span class="tool-count" id="result-count"></span>
  </div>
</div>

<div class="workspace">
  <main class="schedule">
    <div id="schedule"></div>
  </main>
  <aside class="rail">
    <div class="rail-head"><h2>Recent changes</h2></div>
    <div class="win" id="win"></div>
    <div id="rail-list"></div>
  </aside>
</div>

<div class="foot">
  Source: NYC Council via the Legistar API. Times and locations can change &mdash; confirm on the official agenda before attending.
</div>

<script>window.__DATA__ = {data_json};</script>
<script>{js}</script>
</body>
</html>
"""


def _write_error_page(message, timestamp=None):
    os.makedirs(WEB_DIR, exist_ok=True)
    ts = timestamp or datetime.now().isoformat()
    try:
        ts_disp = datetime.fromisoformat(ts).strftime("%b %-d, %Y · %-I:%M %p")
    except (ValueError, TypeError):
        ts_disp = ts
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NYC Council Hearings</title>
{FONT_LINKS}
<style>
body {{ margin:0; font-family:'Libre Franklin',-apple-system,BlinkMacSystemFont,sans-serif;
  background:#f4f1ea; color:#1b1a17; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
.box {{ max-width:460px; padding:32px; border-top:2px solid #1b1a17; }}
.k {{ font-family:'Spline Sans Mono',monospace; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#97948a; }}
h1 {{ font-size:20px; margin:6px 0 10px; }}
p {{ color:#46443d; font-size:14px; margin:0 0 6px; }}
.ts {{ font-family:'Spline Sans Mono',monospace; color:#97948a; font-size:12px; margin-top:16px; }}
</style></head>
<body><div class="box">
<div class="k">New York City Council</div>
<h1>Hearing data is temporarily unavailable</h1>
<p>{message}</p>
<p>The schedule will reappear automatically once the next update succeeds.</p>
<div class="ts">Last attempt: {ts_disp}</div>
</div></body></html>"""
    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="Generate the static hearings web page.")
    parser.add_argument("--title", default="NYC Council Hearings", help="Title for the HTML page.")
    parser.add_argument("--updates-filter",
                        choices=["since_last_run", "last_7_days", "last_30_days"],
                        default="since_last_run",
                        help="Default updates window shown in the changes rail.")
    parser.add_argument("--input", default=PROCESSED_EVENTS_FILE, help="Path to the processed events JSON.")
    parser.add_argument("--output", default=INDEX_HTML, help="Path to write the HTML page.")
    args = parser.parse_args()

    logger.info("Starting webpage generation...")

    if not os.path.exists(args.input):
        logger.error(f"Processed events file not found: {args.input}")
        _write_error_page("The data file could not be found.")
        return

    try:
        with open(args.input, 'r') as f:
            processed_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading processed events data: {e}")
        _write_error_page("The data file could not be read.")
        return

    if "error" in processed_data and processed_data.get("error"):
        logger.warning(f"Data file indicates an upstream error: {processed_data['error']}")
        _write_error_page(str(processed_data["error"]), processed_data.get("generation_timestamp"))
        return

    final_html = generate_html_page_content(
        processed_data, page_title=args.title, updates_filter_value=args.updates_filter,
    )

    out_dir = os.path.dirname(args.output) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(final_html)

    logger.info(f"Successfully generated webpage at {args.output} "
                f"({len(processed_data.get('upcoming_hearings', []))} hearings).")


if __name__ == "__main__":
    main()
