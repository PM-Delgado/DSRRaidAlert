# Overview

This is a Discord webhook notification bot for Dark and Darker raids. The application monitors raid schedule information from dsrwiki.com and sends automated alerts to a Discord channel when raids are approaching. It scrapes raid timing and map information from the website and manages timezone conversions between KST (Korean Standard Time) and other timezones for accurate notifications.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Components

**Web Scraping Module**: Uses BeautifulSoup4 to parse HTML content from dsrwiki.com and extract raid timing information. The scraper looks for specific HTML elements containing raid schedules and map names.

**Timezone Management**: Implements pytz library for accurate timezone handling, specifically converting between KST (Korea Standard Time) and local times to ensure raid alerts are sent at the correct moments.

**Notification System**: Utilizes Discord webhooks for real-time notifications. The system formats and sends structured messages to Discord channels when raids are detected or approaching.

**Scheduling Engine**: Runs continuous monitoring with configurable intervals (currently 60 seconds) to check for raid updates and trigger appropriate notifications.

## Data Flow

The application follows a simple polling architecture:
1. Fetches raid data from the target website at regular intervals
2. Parses HTML content to extract raid times and map information  
3. Converts times to appropriate timezone format
4. Sends webhook notifications to Discord when conditions are met

## Error Handling

Implements basic error handling for web scraping failures, parsing errors, and webhook delivery issues. The system continues operation even when individual requests fail.

# External Dependencies

**Discord Webhooks**: Primary notification delivery mechanism requiring webhook URL configuration through environment variables.

**dsrwiki.com**: Target website for raid schedule information. The application depends on the site's HTML structure remaining consistent for successful data extraction.

**Python Libraries**:
- `requests`: HTTP client for web scraping and webhook delivery
- `beautifulsoup4`: HTML parsing and data extraction
- `pytz`: Timezone conversion and management

**Environment Configuration**: Requires `DISCORD_WEBHOOK` environment variable for webhook URL configuration.