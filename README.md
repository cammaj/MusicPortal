# MusicPortal

MusicPortal is a university project designed to bridge the gap between music artists and their fans. It serves as a comprehensive platform where bands can schedule concerts, fans can discover events and purchase tickets, and administrators can oversee the entire ecosystem.

## Features

### For Fans
- **Discover Concerts**: Search for concerts by artist, date, status, or location.
- **Ticket Purchase**: Buy tickets for upcoming shows (with automatic sold-out detection).
- **Favorites**: Save interesting concerts to a "Selected" list.
- **Dashboard**: View purchased tickets and history.
- **Location Detection**: Automatically detect your city to find local gigs.

### For Bands
- **Concert Management**: Create, edit, and manage concert listings.
- **Dashboard**: Overview of scheduled events.
- **Profile**: Manage band profile and image.

### For Administrators
- **User Management**: Edit user roles, update profiles, and reset passwords.
- **Concert Oversight**: Edit or delete any concert, manage statuses (Scheduled, Cancelled, Sold Out).
- **Activity Logging**: Automatic logging of administrative actions to text files.
- **Dashboard**: Centralized control panel for system management.

## Tech Stack

- **Backend**: Python (Flask)
- **Database**: SQLite
- **Frontend**: HTML5, CSS3 (Glassmorphism design), JavaScript
- **Authentication**: Werkzeug security

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/cammaj/MusicPortal.git
   cd MusicPortal
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   Open your browser and navigate to `http://localhost:5000`.

## Usage

- **Default Admin Credentials**:
  - Username: `admin`
  - Password: `1234`

- **Demo Data**: The application initializes with a set of demo bands and concerts for testing purposes.

## Project Structure

```
MusicPortal/
├── app.py              # Main application entry point
├── musicportal.db      # SQLite database
├── requirements.txt    # Python dependencies
├── static/             # CSS, Images, Uploads
├── templates/          # HTML Templates
└── utils/              # Utility scripts
```

## Copyright

© 2025 MusicPortal Project. All Rights Reserved.
Created by Kamil Gzyl (cammaj).
