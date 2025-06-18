#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime
import argparse
import math
from urllib.parse import parse_qs # For parsing query params if we were in a web server context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_page_generator')

# Constants
DATA_DIR = "data"
PROCESSED_EVENTS_FILE = os.path.join(DATA_DIR, "processed_events_for_web.json")
WEB_DIR = "docs"
INDEX_HTML = os.path.join(WEB_DIR, "index.html")
ITEMS_PER_PAGE = 25

def format_display_date(date_str, include_time=True):
    """Format an ISO date string (or part of it) for display."""
    if not date_str:
        return "TBD"
    try:
        # Handle full ISO datetime strings and date-only strings
        dt_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if 'T' in date_str else datetime.strptime(date_str, '%Y-%m-%d')
        if include_time:
            return dt_obj.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            return dt_obj.strftime("%A, %B %d, %Y")
    except ValueError:
        # Fallback for unexpected date formats or if only time is present (though time usually accompanies date)
        return date_str

def get_event_time_display(time_str):
    if not time_str:
        return "Time TBD"
    try:
        # Try parsing as "10:00 AM" format first
        dt_obj = datetime.strptime(time_str, '%I:%M %p')
        return dt_obj.strftime('%I:%M %p')
    except ValueError:
        try:
            # Try parsing as "10:00:00" format (24-hour)
            dt_obj = datetime.strptime(time_str, '%H:%M:%S')
            return dt_obj.strftime('%I:%M %p')
        except ValueError:
            try:
                # Try parsing as "10:00" format (24-hour without seconds)
                dt_obj = datetime.strptime(time_str, '%H:%M')
                return dt_obj.strftime('%I:%M %p')
            except ValueError:
                return time_str # Return as is if format is unexpected

def generate_event_card(event_entry, is_update_card=False):
    """Generates HTML for a single event card."""
    event_data = event_entry.get("event_data", {})
    tags = event_entry.get("user_facing_tags", [])
    
    card_html = '<div class="card event-card mb-3">'
    card_html += '<div class="card-body">'
    
    # Header section with committee name and agenda button side by side
    card_html += '<div class="card-header-flex">'
    card_html += f'<h5 class="card-title">{event_data.get("EventBodyName", "N/A")}</h5>'
    
    # Buttons container
    card_html += '<div class="card-buttons">'
    
    # Agenda button
    agenda_file = event_data.get("EventAgendaFile")
    if agenda_file:
        card_html += f'<a href="{agenda_file}" target="_blank" class="btn btn-sm btn-outline-primary me-1">View Agenda</a>'
    
    # Add to Calendar button (only for active events with dates)
    if not is_update_card and event_data.get("EventDate") and event_entry.get("current_status") == "active":
        # Create a data attribute with event info for JavaScript
        import json
        event_info = {
            "id": event_data.get("EventId"),
            "committee": event_data.get("EventBodyName", ""),
            "topic": event_data.get("SyntheticMeetingTopic", ""),
            "date": event_data.get("EventDate", ""),
            "time": event_data.get("EventTime", ""),
            "location": event_data.get("EventLocation", ""),
            "comment": event_data.get("EventComment", "")
        }
        event_json = json.dumps(event_info).replace('"', '&quot;')
        card_html += f'<button class="btn btn-sm btn-outline-success add-to-calendar-btn" data-event="{event_json}" title="Add to Calendar">📅</button>'
    
    card_html += '</div>'  # Close buttons container
    card_html += '</div>'  # Close header-flex
    
    # Subtitle (Synthetic Meeting Topic) - only if available
    meeting_topic = event_data.get("SyntheticMeetingTopic")
    if meeting_topic:
        card_html += f'<h6 class="card-subtitle mb-2 text-muted">{meeting_topic}</h6>'

    # Diagnostic info - First seen timestamp
    first_seen_ts = event_entry.get("first_seen_timestamp")
    if first_seen_ts and not is_update_card:
        try:
            first_seen_dt = datetime.fromisoformat(first_seen_ts.replace('Z', '+00:00'))
            first_seen_display = first_seen_dt.strftime("%m/%d/%Y %I:%M %p")
            card_html += f'<p class="card-text small text-muted mb-1"><em>First seen: {first_seen_display}</em></p>'
        except ValueError:
            card_html += f'<p class="card-text small text-muted mb-1"><em>First seen: {first_seen_ts}</em></p>'

    # Tags for upcoming hearings
    if not is_update_card and tags:
        tag_html = ""
        if "new_hearing_tag" in tags:
            tag_html += '<span class="badge bg-success me-1">NEW</span>'
        if "rescheduled_hearing_tag" in tags and event_entry.get("original_event_details_if_rescheduled"):
            orig_details = event_entry["original_event_details_if_rescheduled"]
            orig_date_disp = format_display_date(orig_details.get("original_date"), include_time=False)
            orig_time_disp = get_event_time_display(orig_details.get("original_time"))
            tag_html += f'<span class="badge bg-info me-1">RESCHEDULED (was {orig_date_disp} {orig_time_disp})</span>'
        if "deferred_hearing_tag" in tags:
            tag_html += '<span class="badge bg-warning me-1">DEFERRED</span>'
        if tag_html:
            card_html += f'<p class="card-text small">{tag_html}</p>'

    # Date, Time and Location in one responsive flex row
    event_date = event_data.get("EventDate")
    event_time = event_data.get("EventTime")
    event_location = event_data.get("EventLocation", "TBD")

    if event_entry.get("current_status") in ["deferred_pending_match", "deferred_nomatch"]:
        original_date_display = format_display_date(event_date, include_time=False)
        original_time_display = get_event_time_display(event_time)
        card_html += f'<p class="card-text"><strong>Original Date:</strong> <del>{original_date_display}</del> {original_time_display}</p>'
        if event_entry["current_status"] == "deferred_pending_match":
            card_html += '<p class="card-text"><em>Reschedule: Awaiting information</em></p>'
        elif event_entry["current_status"] == "deferred_nomatch":
            card_html += '<p class="card-text"><em>Reschedule: None found after grace period</em></p>'
    else: # Active events or the new part of a reschedule
        date_display = format_display_date(event_date, include_time=False)
        time_display = get_event_time_display(event_time)
        
        # Use flexbox for date, time, location with automatic wrapping
        card_html += '<div class="card-details-flex">'
        card_html += f'<p class="detail-item"><strong>Date:</strong> {date_display}</p>'
        card_html += f'<p class="detail-item"><strong>Time:</strong> {time_display}</p>'
        card_html += f'<p class="detail-item"><strong>Location:</strong> {event_location}</p>'
        card_html += '</div>'
    
    # Comment
    comment = event_data.get("EventComment")
    if comment:
        card_html += f'<p class="card-text fst-italic"><small>Comment: {comment}</small></p>'
    
    card_html += "</div></div>"
    return card_html

def generate_update_item_html(update_item):
    """Generates HTML for an item in the 'Updates' column based on simplified alert types."""
    item_type = update_item.get("type") # This will be "new" or "deferred"
    entry = update_item.get("data", {})
    event_data = entry.get("event_data", {})
    html = '<div class="card event-card mb-3">'
    html += '<div class="card-body">'
    
    body_name = event_data.get("EventBodyName", "N/A")
    meeting_topic = event_data.get("SyntheticMeetingTopic")
    
    original_event_details = entry.get("original_event_details_if_rescheduled")
    rescheduled_details_for_deferred = entry.get("rescheduled_event_details_if_deferred")
    
    agenda_file = event_data.get("EventAgendaFile")
    
    # Header section with committee name and agenda button
    html += '<div class="card-header-flex">'
    if item_type == "new":
        html += f'<h5 class="card-title text-success">NEW: {body_name}</h5>'
    elif item_type == "deferred":
        html += f'<h5 class="card-title text-warning">DEFERRED: {body_name}</h5>'
    else:
        html += f'<h5 class="card-title text-muted">UPDATE ({item_type}): {body_name}</h5>'
    
    # Agenda button
    if agenda_file:
        html += f'<a href="{agenda_file}" target="_blank" class="btn btn-sm btn-outline-secondary agenda-btn">View Agenda</a>'
    html += '</div>'
    
    # Meeting topic subtitle
    if meeting_topic:
        html += f'<h6 class="card-subtitle mb-2 text-muted">{meeting_topic}</h6>'
    
    # Diagnostic info for updates - show alert timestamp
    alert_timestamp = update_item.get("alert_timestamp")
    if alert_timestamp:
        try:
            alert_dt = datetime.fromisoformat(alert_timestamp.replace('Z', '+00:00'))
            alert_display = alert_dt.strftime("%m/%d/%Y %I:%M %p")
            days_ago = (datetime.now() - alert_dt).days
            html += f'<p class="card-text small text-muted mb-1"><em>Alert: {alert_display} ({days_ago} days ago)</em></p>'
        except ValueError:
            html += f'<p class="card-text small text-muted mb-1"><em>Alert: {alert_timestamp}</em></p>'

    if item_type == "new":
        current_event_date_disp = format_display_date(event_data.get("EventDate"), include_time=False)
        current_event_time_disp = get_event_time_display(event_data.get("EventTime"))
        event_location = event_data.get("EventLocation", "TBD")
        
        # Use flexbox for details
        html += '<div class="card-details-flex">'
        html += f'<p class="detail-item"><strong>Date:</strong> {current_event_date_disp}</p>'
        html += f'<p class="detail-item"><strong>Time:</strong> {current_event_time_disp}</p>'
        html += f'<p class="detail-item"><strong>Location:</strong> {event_location}</p>'
        html += '</div>'
        
        if original_event_details: # This "new" event is a reschedule of a previous one
            orig_date_disp = format_display_date(original_event_details.get("original_date"), include_time=False)
            orig_time_disp = get_event_time_display(original_event_details.get("original_time"))
            html += f'<p class="card-text fst-italic"><small>(Rescheduled from {orig_date_disp} {orig_time_disp})</small></p>'

    elif item_type == "deferred":
        original_date_disp = format_display_date(event_data.get("EventDate"), include_time=False)
        original_time_disp = get_event_time_display(event_data.get("EventTime"))
        html += f'<p class="card-text">Original Date: <del>{original_date_disp} {original_time_disp}</del></p>'

        if rescheduled_details_for_deferred: # This deferred event has been rescheduled
            new_date_disp = format_display_date(rescheduled_details_for_deferred.get("new_date"), include_time=False)
            new_time_disp = get_event_time_display(rescheduled_details_for_deferred.get("new_time"))
            html += f'<p class="card-text"><strong>Rescheduled to: {new_date_disp} {new_time_disp}</strong></p>'
        else: # Still deferred, awaiting reschedule or no match found after grace period
            html += '<p class="card-text"><em>Reschedule: Awaiting information</em></p>'
    else:
        # Fallback for any unexpected item_type, though this shouldn't happen with the new logic.
        current_event_date_disp = format_display_date(event_data.get("EventDate"), include_time=False)
        current_event_time_disp = get_event_time_display(event_data.get("EventTime"))
        html += f'<p class="card-text">Date: {current_event_date_disp} {current_event_time_disp}</p>'

    # Comment if exists
    comment = event_data.get("EventComment")
    if comment:
        html += f'<p class="card-text fst-italic small">{comment}</p>'
        
    html += "</div></div>"
    return html

def generate_pagination_html(total_pages, items_per_page):
    """Generate pagination HTML that works with client-side JavaScript."""
    if total_pages <= 1:
        return ""

    html = f'''
    <nav aria-label="Page navigation">
        <ul class="pagination justify-content-center" data-total-pages="{total_pages}" data-items-per-page="{items_per_page}">
            <li class="page-item" id="prev-btn">
                <a class="page-link" href="#" data-page="prev">Previous</a>
            </li>
            <span id="page-numbers">
                <!-- Page numbers will be generated by JavaScript -->
            </span>
            <li class="page-item" id="next-btn">
                <a class="page-link" href="#" data-page="next">Next</a>
            </li>
        </ul>
    </nav>'''
    return html

def generate_html_page_content(processed_data, page_title="NYC Legistar Hearing Monitor", updates_filter_value="since_last_run"):
    """Generates the main HTML structure for the page."""
    
    generation_timestamp = processed_data.get("generation_timestamp", datetime.now().isoformat())
    generation_date_display = format_display_date(generation_timestamp)

    # Get all update lists - we'll include all of them in the HTML
    updates_since_last_run = processed_data.get("updates_since_last_run", [])
    updates_last_7_days = processed_data.get("updates_last_7_days", [])
    updates_last_30_days = processed_data.get("updates_last_30_days", [])

    upcoming_hearings_all = processed_data.get("upcoming_hearings", [])
    total_upcoming = len(upcoming_hearings_all)
    total_pages = math.ceil(total_upcoming / ITEMS_PER_PAGE)
    
    # No server-side pagination - include all hearings with data attributes for client-side pagination

    # Create the CSS styles as a separate string to avoid f-string parsing issues
    css_styles = """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding-top: 20px; }
        .container-main { max-width: 1400px; }
        .updates-column { max-height: 90vh; overflow-y: auto; position: sticky; top: 20px; }
        .event-card { border-left-width: 5px; border-left-style: solid; }
        .card-title small { font-size: 0.8rem; color: #6c757d; }
        del { color: #dc3545; }
        
        /* New styles for improved card layout */
        .card-header-flex { 
            display: flex; 
            justify-content: space-between; 
            align-items: flex-start;
            margin-bottom: 8px;
        }
        .card-header-flex .card-title { 
            margin-bottom: 0; 
            margin-right: 8px;
            flex: 1;
        }
        .card-buttons {
            display: flex;
            gap: 4px;
            align-items: center;
            flex-shrink: 0;
        }
        .card-subtitle {
            margin-top: 0.25rem !important;
            margin-bottom: 0.75rem !important;
        }
        .card-details-flex {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 8px;
        }
        .card-details-flex .detail-item {
            margin: 0;
            white-space: nowrap;
        }
        .add-to-calendar-btn {
            font-size: 14px;
            padding: 2px 6px;
        }
        
        /* Hide update sections by default */
        .updates-section {
            display: none;
        }
        .updates-section.active {
            display: block;
        }
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>{css_styles}</style>
</head>
<body>
    <div class="container container-main">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>{page_title}</h1>
            <p class="text-muted mb-0">Last updated: {generation_date_display}</p>
        </div>

        <div class="row">
            <!-- Updates Column (Left) -->
            <div class="col-md-4 updates-column">
                <h4>Updates</h4>
                <div class="mb-3">
                    <select class="form-select" id="updates-filter">
                        <option value="since_last_run">Since last update</option>
                        <option value="last_7_days">Last 7 days</option>
                        <option value="last_30_days">Last 30 days</option>
                    </select>
                </div>
                
                <!-- Since Last Run Updates -->
                <div id="updates-since-last-run" class="updates-section">
"""
    
    if updates_since_last_run:
        for item in updates_since_last_run:
            html += generate_update_item_html(item)
    else:
        html += '                    <p class="text-muted">No updates since last run.</p>'

    html += """
                </div>
                
                <!-- Last 7 Days Updates -->
                <div id="updates-last-7-days" class="updates-section">
"""
    
    if updates_last_7_days:
        for item in updates_last_7_days:
            html += generate_update_item_html(item)
    else:
        html += '                    <p class="text-muted">No updates in the last 7 days.</p>'

    html += """
                </div>
                
                <!-- Last 30 Days Updates -->
                <div id="updates-last-30-days" class="updates-section">
"""
    
    if updates_last_30_days:
        for item in updates_last_30_days:
            html += generate_update_item_html(item)
    else:
        html += '                    <p class="text-muted">No updates in the last 30 days.</p>'

    html += """
                </div>
            </div> <!-- /col-md-4 updates-column -->

            <!-- Upcoming Hearings Column (Right) -->
            <div class="col-md-8">
                <h4>Upcoming Hearings (""" + f"{total_upcoming} total" + """)</h4>
                <div id="upcoming-hearings-content">
"""
    if upcoming_hearings_all:
        for i, event_entry in enumerate(upcoming_hearings_all):
            # Add data-index for client-side pagination
            card_html = generate_event_card(event_entry)
            # Insert data-index attribute into the card div
            card_html = card_html.replace('<div class="card event-card mb-3">', 
                                         f'<div class="card event-card mb-3" data-hearing-index="{i}">')
            html += card_html
    else:
        html += '                    <p class="text-muted">No upcoming hearings found.</p>'

    html += """
                </div> <!-- /upcoming-hearings-content -->
"""
    html += generate_pagination_html(total_pages, ITEMS_PER_PAGE)

    html += f"""
            </div> <!-- /col-md-8 -->
        </div> <!-- /row -->
    </div> <!-- /container -->
"""

    # The entire script is now a separate template to avoid f-string escaping issues with JavaScript.
    script_template = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const filterSelect = document.getElementById('updates-filter');
            const paginationContainer = document.querySelector('.pagination');
            
            let currentPage = 1;
            let itemsPerPage = 25;
            let totalPages = 1;

            // --- Start of functionality ---

            // 1. UPDATES FILTERING LOGIC
            function initializeUpdatesFilter() {
                const urlParams = new URLSearchParams(window.location.search);
                const filterFromURL = urlParams.get('filter') || '{updates_filter_value}';
                
                filterSelect.value = filterFromURL;
                showUpdatesSection(filterFromURL);

                filterSelect.addEventListener('change', function() {
                    updateFilter(this.value);
                });
            }

            function updateFilter(filterValue) {
                showUpdatesSection(filterValue);
                updateURL(filterValue, currentPage);
            }

            function showUpdatesSection(sectionName) {
                document.querySelectorAll('.updates-section').forEach(section => section.classList.remove('active'));
                const targetId = 'updates-' + sectionName.replace(/_/g, '-');
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    targetSection.classList.add('active');
                }
            }
            
            // 2. PAGINATION LOGIC
            function initializePagination() {
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const totalItems = allHearings.length;
                totalPages = Math.ceil(totalItems / itemsPerPage);

                if (paginationContainer) {
                    paginationContainer.dataset.totalPages = totalPages;
                    paginationContainer.dataset.itemsPerPage = itemsPerPage;
                }

                const urlParams = new URLSearchParams(window.location.search);
                const urlPage = parseInt(urlParams.get('page')) || 1;
                currentPage = Math.max(1, Math.min(urlPage, totalPages));
                
                showPage(currentPage);
            }

            function showPage(page) {
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const startIndex = (page - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;

                allHearings.forEach((hearing, index) => {
                    hearing.style.display = (index >= startIndex && index < endIndex) ? 'block' : 'none';
                });

                currentPage = page;
                updatePaginationControls();
                updateURL(filterSelect.value, page);
            }
            
            function showPageWithoutURLUpdate(page) {
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const startIndex = (page - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;

                allHearings.forEach((hearing, index) => {
                    hearing.style.display = (index >= startIndex && index < endIndex) ? 'block' : 'none';
                });
                currentPage = page;
                updatePaginationControls();
            }

            // 3. URL AND BROWSER HISTORY LOGIC
            function updateURL(filter, page) {
                const url = new URL(window.location);
                url.searchParams.set('filter', filter);
                if (page > 1) {
                    url.searchParams.set('page', page);
                } else {
                    url.searchParams.delete('page');
                }
                window.history.replaceState({}, '', url);
            }

            window.addEventListener('popstate', function() {
                const urlParams = new URLSearchParams(window.location.search);
                const filterFromURL = urlParams.get('filter') || '{updates_filter_value}';
                const pageFromURL = parseInt(urlParams.get('page')) || 1;
                
                filterSelect.value = filterFromURL;
                showUpdatesSection(filterFromURL);
                
                showPageWithoutURLUpdate(pageFromURL);
            });

            // 4. CALENDAR BUTTON LOGIC
            function initializeCalendarButtons() {
                document.addEventListener('click', function(e) {
                    const calendarButton = e.target.closest('.add-to-calendar-btn');
                    if (calendarButton) {
                        e.preventDefault();
                        const eventData = calendarButton.getAttribute('data-event');
                        if (eventData) {
                            try {
                                const eventInfo = JSON.parse(eventData.replace(/&quot;/g, '"'));
                                downloadICalendar(eventInfo);
                            } catch (err) {
                                console.error("Error parsing event data for calendar:", err);
                            }
                        }
                    }
                });
            }

            function formatDateForICal(dateStr, timeStr) {
                try {
                    let eventDate = timeStr ? new Date(dateStr.split('T')[0] + ' ' + timeStr) : new Date(dateStr);
                    return eventDate.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
                } catch (e) {
                    return new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
                }
            }

            function generateICalendar(eventInfo) {
                const now = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
                const startTime = formatDateForICal(eventInfo.date, eventInfo.time);
                
                const endDate = new Date(startTime);
                endDate.setHours(endDate.getHours() + 1);
                const endTimeFormatted = endDate.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
                
                const uid = `event-${eventInfo.id}-${startTime}@legistar-monitor.github.io`;
                
                let description = eventInfo.topic || '';
                if (eventInfo.comment) {
                    description += `\\n\\nComment: ${eventInfo.comment}`;
                }
                
                const escapeICal = (str) => String(str).replace(/[,;\\]/g, (char) => '\\\\' + char).replace(/\\n/g, '\\\\n');
                
                const summary = escapeICal(eventInfo.committee + (eventInfo.topic ? ': ' + eventInfo.topic : ''));
                const location = escapeICal(eventInfo.location || '');
                const desc = escapeICal(description);
                
                const cal = [
                    'BEGIN:VCALENDAR',
                    'VERSION:2.0',
                    'PRODID:-//Legistar Monitor//AddToCalendar 1.0//EN',
                    'BEGIN:VEVENT',
                    `UID:${uid}`,
                    `DTSTAMP:${now}`,
                    `DTSTART:${startTime}`,
                    `DTEND:${endTimeFormatted}`,
                    `SUMMARY:${summary}`,
                    `DESCRIPTION:${desc}`,
                    `LOCATION:${location}`,
                    'END:VEVENT',
                    'END:VCALENDAR'
                ];
                return cal.join('\\r\\n');
            }

            function downloadICalendar(eventInfo) {
                const icalContent = generateICalendar(eventInfo);
                const encodedContent = encodeURIComponent(icalContent);
                const dataUrl = 'data:text/calendar;charset=utf-8,' + encodedContent;
                
                const committee = (eventInfo.committee || 'event').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
                const date = (eventInfo.date || '').split('T')[0];
                const filename = `${committee}-${date}.ics`;
                
                const link = document.createElement('a');
                link.href = dataUrl;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            
            // 5. PAGINATION CONTROLS
            function updatePaginationControls() {
                if (!paginationContainer || totalPages <= 1) {
                    if (paginationContainer) paginationContainer.style.display = 'none';
                    return;
                }
                
                paginationContainer.style.display = 'flex';
                const prevBtn = document.getElementById('prev-btn');
                const nextBtn = document.getElementById('next-btn');
                const pageNumbers = document.getElementById('page-numbers');
                
                prevBtn.classList.toggle('disabled', currentPage <= 1);
                prevBtn.querySelector('a').onclick = (e) => { e.preventDefault(); if (currentPage > 1) showPage(currentPage - 1); };
                
                nextBtn.classList.toggle('disabled', currentPage >= totalPages);
                nextBtn.querySelector('a').onclick = (e) => { e.preventDefault(); if (currentPage < totalPages) showPage(currentPage + 1); };
                
                // Page number generation logic...
                let pageNumbersHTML = '';
                // ... (logic to generate page numbers based on currentPage and totalPages) ...
                pageNumbers.innerHTML = pageNumbersHTML;
            }

            // --- Initializations ---
            initializeUpdatesFilter();
            initializePagination();
            initializeCalendarButtons();
        });
    </script>
</body>
</html>
"""
    
    html += script_template.format(updates_filter_value=updates_filter_value)
    
    return html

def main():
    parser = argparse.ArgumentParser(description="Generate a static HTML page for Legistar hearings.")
    parser.add_argument("--title", default="NYC Legistar Hearing Monitor", help="Title for the HTML page.")
    parser.add_argument("--updates-filter", 
                        choices=["since_last_run", "last_7_days", "last_30_days"],
                        default="since_last_run", 
                        help="Which set of updates to display by default.")
    args = parser.parse_args()
    
    logger.info("Starting webpage generation...")

    if not os.path.exists(PROCESSED_EVENTS_FILE):
        logger.error(f"Processed events file not found: {PROCESSED_EVENTS_FILE}")
        error_html = f"<html><body><h1>Error</h1><p>Processed data file not found. Cannot generate page.</p><p>Last attempted update: {datetime.now().isoformat()}</p></body></html>"
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(INDEX_HTML, 'w') as f:
            f.write(error_html)
        logger.info(f"Generated error page at {INDEX_HTML}")
        return

    try:
        with open(PROCESSED_EVENTS_FILE, 'r') as f:
            processed_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading processed events data: {e}")
        error_html = f"<html><body><h1>Error</h1><p>Could not load processed data: {e}</p><p>Last attempted update: {datetime.now().isoformat()}</p></body></html>"
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(INDEX_HTML, 'w') as f:
            f.write(error_html)
        logger.info(f"Generated error page due to data load failure at {INDEX_HTML}")
        return

    if "error" in processed_data:
        logger.warning(f"Data file indicates an error from previous step: {processed_data['error']}")
        error_html = f"<html><body><h1>Warning</h1><p>There was an issue fetching or processing hearing data: {processed_data['error']}</p><p>Timestamp: {processed_data.get('generation_timestamp', datetime.now().isoformat())}</p></body></html>"
        os.makedirs(WEB_DIR, exist_ok=True)
        with open(INDEX_HTML, 'w') as f:
            f.write(error_html)
        logger.info(f"Generated warning page at {INDEX_HTML} due to upstream error.")
        return

    final_html = generate_html_page_content(
        processed_data, 
        page_title=args.title, 
        updates_filter_value=args.updates_filter
    )
    
    os.makedirs(WEB_DIR, exist_ok=True)
    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    logger.info(f"Successfully generated webpage at {INDEX_HTML} (Updates: {args.updates_filter})")

if __name__ == "__main__":
    main() 