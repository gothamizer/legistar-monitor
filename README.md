# NYC Legistar Hearing Monitor

Automated monitoring system for NYC City Council hearings via the Legistar API.

## Features

- **Automatic Detection**: Monitors new hearings, deferrals, and reschedules
- **Smart Matching**: Links deferred hearings to their rescheduled counterparts using exact topic matching
- **Web Interface**: Clean, responsive interface showing upcoming hearings and recent updates
- **GitHub Pages Deployment**: Automatically deploys to a static website

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd legistar-monitor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration** (optional)
   Create `config.json` to override defaults:
   ```json
   {
     "hearing_monitor_settings": {
       "lookback_days": 365
     }
   }
   ```

## Usage

### Manual Operation

1. **Check for new hearings**
   ```bash
   python check_new_hearings.py
   ```

2. **Generate web page**
   ```bash
   python generate_web_page.py
   ```

### Automated Operation

The system is designed to run via GitHub Actions on a schedule. The workflow:
1. Runs `check_new_hearings.py` to fetch and process hearing data
2. Runs `generate_web_page.py` to create the web interface
3. Deploys the results to GitHub Pages

## Files

- `check_new_hearings.py` - Main monitoring script
- `generate_web_page.py` - Web interface generator  
- `legistar_api.py` - Legistar API client
- `requirements.txt` - Python dependencies
- `.github/workflows/` - GitHub Actions automation

## Data Storage

- `data/seen_events.json` - Persistent storage of hearing data and states
- `data/processed_events_for_web.json` - Web-ready data generated for display

## License

MIT License
