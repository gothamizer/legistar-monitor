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
    
    # Header section with committee name and buttons side by side
    card_html += '<div class="card-header-flex">'
    card_html += f'<h5 class="card-title">{event_data.get("EventBodyName", "N/A")}</h5>'
    
    # Button group for agenda and calendar
    card_html += '<div class="btn-group-custom">'
    
    # Agenda button
    agenda_file = event_data.get("EventAgendaFile")
    if agenda_file:
        card_html += f'<a href="{agenda_file}" target="_blank" class="btn btn-sm btn-outline-primary me-1">View Agenda</a>'
    
    # Add to Calendar button (only for active events with valid dates)
    if (not is_update_card and 
        event_entry.get("current_status") == "active" and 
        event_data.get("EventDate")):
        event_id = event_data.get("EventId", "unknown")
        card_html += f'<button class="btn btn-sm btn-outline-success" onclick="addToCalendar({event_id})">Add to Calendar</button>'
    
    card_html += '</div></div>'
    
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
        .btn-group-custom {
            display: flex;
            gap: 4px;
            flex-shrink: 0;
        }
        .btn-group-custom .btn {
            white-space: nowrap;
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

    <script>
        // Store event data for calendar generation
        const eventData = {{}};
        
        // Function to generate and download iCalendar file
        function addToCalendar(eventId) {{
            const event = eventData[eventId];
            if (!event) {{
                alert('Event data not found');
                return;
            }}
            
            const icalString = generateICalendar(event);
            const encodedString = encodeURIComponent(icalString);
            const dataUrl = 'data:text/calendar;charset=utf-8,' + encodedString;
            
            // Create temporary link and trigger download
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = `hearing-${{eventId}}.ics`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
        
        // Generate iCalendar string
        function generateICalendar(event) {{
            const now = new Date();
            const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            
            // Parse event date and time
            const eventDateTime = parseEventDateTime(event.EventDate, event.EventTime);
            const startTime = eventDateTime.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            
            // Assume 1-hour duration if not specified
            const endDateTime = new Date(eventDateTime.getTime() + 60 * 60 * 1000);
            const endTime = endDateTime.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            
            // Generate unique UID
            const uid = `${{startTime}}-${{event.EventId}}@legistar-monitor.github.io`;
            
            // Prepare description
            let description = event.SyntheticMeetingTopic || 'NYC Council Hearing';
            if (event.EventComment) {{
                description += '\\n\\nComment: ' + event.EventComment;
            }}
            
            // Build iCalendar content with proper line wrapping
            let ical = [
                'BEGIN:VCALENDAR',
                'VERSION:2.0',
                'PRODID:-//NYC Legistar Monitor//Hearing Calendar 1.0//EN',
                'METHOD:PUBLISH',
                'BEGIN:VEVENT',
                `UID:${{uid}}`,
                `DTSTAMP:${{timestamp}}`,
                `DTSTART:${{startTime}}`,
                `DTEND:${{endTime}}`,
                wrapICalLine(`SUMMARY:${{event.EventBodyName}}`),
                wrapICalLine(`DESCRIPTION:${{description}}`),
                wrapICalLine(`LOCATION:${{event.EventLocation || 'TBD'}}`),
                'END:VEVENT',
                'END:VCALENDAR'
            ];
            
            return ical.join('\\r\\n');
        }}
        
        // Parse event date and time into JavaScript Date object
        function parseEventDateTime(dateStr, timeStr) {{
            if (!dateStr) return new Date();
            
            // Remove time part from date if present
            const datePart = dateStr.split('T')[0];
            
            if (!timeStr) {{
                // If no time specified, use 12:00 PM
                return new Date(`${{datePart}}T12:00:00`);
            }}
            
            try {{
                // Try to parse time (handle "10:00 AM" format)
                const timeParts = timeStr.match(/(\\d{{1,2}}):(\\d{{2}})\\s*(AM|PM)/i);
                if (timeParts) {{
                    let hours = parseInt(timeParts[1]);
                    const minutes = parseInt(timeParts[2]);
                    const ampm = timeParts[3].toUpperCase();
                    
                    if (ampm === 'PM' && hours !== 12) hours += 12;
                    if (ampm === 'AM' && hours === 12) hours = 0;
                    
                    const timeString = `${{hours.toString().padStart(2, '0')}}:${{minutes.toString().padStart(2, '0')}}:00`;
                    return new Date(`${{datePart}}T${{timeString}}`);
                }}
                
                // Fallback to combining date and time as-is
                return new Date(`${{datePart}}T${{timeStr}}`);
            }} catch (e) {{
                // If parsing fails, use date with 12:00 PM
                return new Date(`${{datePart}}T12:00:00`);
            }}
        }}
        
        // Wrap long iCalendar lines to 75 characters
        function wrapICalLine(line) {{
            if (line.length <= 75) return line;
            
            let wrapped = line.substring(0, 75);
            let remaining = line.substring(75);
            
            while (remaining.length > 0) {{
                wrapped += '\\r\\n '; // Continue with space
                wrapped += remaining.substring(0, 74); // 74 because of the leading space
                remaining = remaining.substring(74);
            }}
            
            return wrapped;
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            const filterSelect = document.getElementById('updates-filter');
            const paginationContainer = document.querySelector('.pagination');
            const hearingsContainer = document.getElementById('upcoming-hearings-content');
            
            let currentPage = 1;
            let itemsPerPage = 25;
            let totalPages = 1;
            
            // Initialize updates filter
            function initializeUpdatesFilter() {{
                // Get filter from URL first, then fall back to default
                const urlParams = new URLSearchParams(window.location.search);
                const filterFromURL = urlParams.get('filter') || '{updates_filter_value}';
                
                filterSelect.value = filterFromURL;
                showUpdatesSection(filterFromURL);
                
                // Add event listener for filter changes
                filterSelect.addEventListener('change', function() {{
                    const selectedValue = this.value;
                    updateFilter(selectedValue);
                }});
            }}
            
            // Update filter and URL
            function updateFilter(filterValue) {{
                showUpdatesSection(filterValue);
                updateURL(filterValue, currentPage);
            }}
            
            // Helper to convert filter name (e.g., 'last_30_days') to section id suffix (e.g., 'last-30-days')
            function filterNameToId(filterName) {{
                return filterName.split('_').join('-'); // replace all underscores with hyphens
            }}
            
            // Show the selected updates section
            function showUpdatesSection(sectionName) {{
                // Hide all sections
                document.querySelectorAll('.updates-section').forEach(section => {{
                    section.classList.remove('active');
                }});
                
                // Show selected section
                const targetSection = document.getElementById('updates-' + filterNameToId(sectionName));
                if (targetSection) {{
                    targetSection.classList.add('active');
                }}
            }}
            
            // Update URL without page reload
            function updateURL(filter, page) {{
                const url = new URL(window.location);
                url.searchParams.set('filter', filter);
                if (page > 1) {{
                    url.searchParams.set('page', page);
                }} else {{
                    url.searchParams.delete('page');
                }}
                window.history.replaceState({{}}, '', url);
            }}
            
            // Initialize pagination
            function initializePagination() {{
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const totalItems = allHearings.length;
                totalPages = Math.ceil(totalItems / itemsPerPage);
                
                if (paginationContainer) {{
                    paginationContainer.dataset.totalPages = totalPages;
                    paginationContainer.dataset.itemsPerPage = itemsPerPage;
                }}
                
                // Get page from URL parameters
                const urlParams = new URLSearchParams(window.location.search);
                const urlPage = parseInt(urlParams.get('page')) || 1;
                currentPage = Math.max(1, Math.min(urlPage, totalPages));
                
                updatePagination();
                showPage(currentPage);
            }}
            
            // Show specific page of hearings
            function showPage(page) {{
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const startIndex = (page - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                
                allHearings.forEach((hearing, index) => {{
                    if (index >= startIndex && index < endIndex) {{
                        hearing.style.display = 'block';
                    }} else {{
                        hearing.style.display = 'none';
                    }}
                }});
                
                currentPage = page;
                updatePagination();
                
                // Update URL with current filter and page
                const currentFilter = filterSelect.value;
                updateURL(currentFilter, page);
            }}
            
            // Update pagination controls
            function updatePagination() {{
                if (!paginationContainer || totalPages <= 1) {{
                    if (paginationContainer) paginationContainer.style.display = 'none';
                    return;
                }}
                
                paginationContainer.style.display = 'block';
                
                const prevBtn = document.getElementById('prev-btn');
                const nextBtn = document.getElementById('next-btn');
                const pageNumbers = document.getElementById('page-numbers');
                
                // Update Previous button
                if (currentPage > 1) {{
                    prevBtn.classList.remove('disabled');
                    prevBtn.querySelector('a').onclick = (e) => {{
                        e.preventDefault();
                        showPage(currentPage - 1);
                    }};
                }} else {{
                    prevBtn.classList.add('disabled');
                    prevBtn.querySelector('a').onclick = (e) => e.preventDefault();
                }}
                
                // Update Next button  
                if (currentPage < totalPages) {{
                    nextBtn.classList.remove('disabled');
                    nextBtn.querySelector('a').onclick = (e) => {{
                        e.preventDefault();
                        showPage(currentPage + 1);
                    }};
                }} else {{
                    nextBtn.classList.add('disabled');
                    nextBtn.querySelector('a').onclick = (e) => e.preventDefault();
                }}
                
                // Generate page numbers
                let pageNumbersHTML = '';
                const startPage = Math.max(1, currentPage - 2);
                const endPage = Math.min(totalPages, currentPage + 2);
                
                if (startPage > 1) {{
                    pageNumbersHTML += `<li class="page-item"><a class="page-link" href="#" onclick="showPage(1); return false;">1</a></li>`;
                    if (startPage > 2) {{
                        pageNumbersHTML += '<li class="page-item disabled"><span class="page-link">...</span></li>';
                    }}
                }}
                
                for (let i = startPage; i <= endPage; i++) {{
                    const activeClass = i === currentPage ? 'active' : '';
                    pageNumbersHTML += `<li class="page-item ${{activeClass}}"><a class="page-link" href="#" onclick="showPage(${{i}}); return false;">${{i}}</a></li>`;
                }}
                
                if (endPage < totalPages) {{
                    if (endPage < totalPages - 1) {{
                        pageNumbersHTML += '<li class="page-item disabled"><span class="page-link">...</span></li>';
                    }}
                    pageNumbersHTML += `<li class="page-item"><a class="page-link" href="#" onclick="showPage(${{totalPages}}); return false;">${{totalPages}}</a></li>`;
                }}
                
                pageNumbers.innerHTML = pageNumbersHTML;
            }}
            
            // Make showPage function global so onclick handlers can access it
            window.showPage = showPage;
            
            // Handle browser back/forward buttons
            window.addEventListener('popstate', function(event) {{
                const urlParams = new URLSearchParams(window.location.search);
                const filterFromURL = urlParams.get('filter') || '{updates_filter_value}';
                const pageFromURL = parseInt(urlParams.get('page')) || 1;
                
                // Update filter dropdown and show section without triggering URL update
                filterSelect.value = filterFromURL;
                showUpdatesSection(filterFromURL);
                
                // Update page without triggering URL update
                currentPage = Math.max(1, Math.min(pageFromURL, totalPages));
                showPageWithoutURLUpdate(currentPage);
            }});
            
            // Show page without updating URL (for back/forward navigation)
            function showPageWithoutURLUpdate(page) {{
                const allHearings = document.querySelectorAll('[data-hearing-index]');
                const startIndex = (page - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                
                allHearings.forEach((hearing, index) => {{
                    if (index >= startIndex && index < endIndex) {{
                        hearing.style.display = 'block';
                    }} else {{
                        hearing.style.display = 'none';
                    }}
                }});
                
                currentPage = page;
                updatePagination();
            }}
            
            // Populate event data for calendar generation
            function populateEventData() {{"""

    # Add event data to JavaScript
    if upcoming_hearings_all:
        for event_entry in upcoming_hearings_all:
            event_data = event_entry.get("event_data", {})
            event_id = event_data.get("EventId")
            if event_id:
                # Escape quotes and newlines in JavaScript strings
                def js_escape(s):
                    if not s:
                        return ""
                    return str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                
                html += f"""
                eventData[{event_id}] = {{
                    EventId: {event_id},
                    EventBodyName: "{js_escape(event_data.get('EventBodyName', ''))}",
                    EventDate: "{js_escape(event_data.get('EventDate', ''))}",
                    EventTime: "{js_escape(event_data.get('EventTime', ''))}",
                    EventLocation: "{js_escape(event_data.get('EventLocation', ''))}",
                    SyntheticMeetingTopic: "{js_escape(event_data.get('SyntheticMeetingTopic', ''))}",
                    EventComment: "{js_escape(event_data.get('EventComment', ''))}"
                }};"""

    html += """
            }}
            
            // Initialize both filters and pagination on page load
            populateEventData();
            initializeUpdatesFilter();
            initializePagination();
        }});
    </script>
</body>
</html>
"""
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
    
    # For a true query param driven site, the GitHub action would need to be smarter or run a small server.
    # For now, the GH Action will always generate index.html with default filters.
    # The JS allows users to change it, and the URL will reflect it for bookmarking/sharing if served appropriately.
    # If different pages per filter are desired (e.g. index_last_7_days.html), main() would need to handle that.

    os.makedirs(WEB_DIR, exist_ok=True)
    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    logger.info(f"Successfully generated webpage at {INDEX_HTML} (Updates: {args.updates_filter})")

if __name__ == "__main__":
    main() 