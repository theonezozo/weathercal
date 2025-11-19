# Weathercal

A Flask-based web service that generates iCalendar (.ics) files with weather forecasts from the National Weather Service (NWS) API. Subscribe to these calendars in your favorite calendar app to see weather conditions as events.

## Features

- **Weather-based calendars**: Generate calendar events for rain, warm weather, cool weather, comfortable conditions, and more
- **Location-based forecasts**: Get weather data for any location in the United States using coordinates
- **Weather alerts**: Subscribe to NWS weather alerts for your area
- **Calendar cleaning**: Remove past events and attendees from existing calendar feeds
- **Auto-refresh**: Caches are automatically refreshed to keep data current

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/theonezozo/weathercal.git
cd weathercal
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

The service will start on `http://localhost:5000`.

### Using with Calendar Apps

To subscribe to a weather calendar:

1. Copy the URL of the endpoint you want (e.g., `http://localhost:5000/weather.ics`)
2. In your calendar app:
   - **Google Calendar**: Click "+" next to "Other calendars" → "From URL" → Paste the URL
   - **Apple Calendar**: File → New Calendar Subscription → Paste the URL
   - **Outlook**: Add calendar → Subscribe from web → Paste the URL

## API Endpoints

### Weather Calendar Endpoints

These endpoints return iCalendar (.ics) files that can be imported into calendar applications.

#### Default Location Endpoints

These endpoints use a default location (Mountain View, CA):

##### `GET /weather.ics`

Returns a calendar with precipitation (rain) forecasts. Events are created for continuous periods where the probability of precipitation exceeds 33%.

**Response**: iCalendar file with rain forecast events

**Example**:
```
GET http://localhost:5000/weather.ics
```

##### `GET /bestweather.ics`

Returns a calendar showing the best weather forecast for each day. The "best" time is determined by:
1. Lowest probability of precipitation
2. Temperature closest to 70°F
3. Lowest wind speed

**Response**: iCalendar file with daily best weather events

**Example**:
```
GET http://localhost:5000/bestweather.ics
```

##### `GET /warm.ics`

Returns a calendar with warm weather periods (≥68°F). Events show when it's good to open windows for warmth.

**Response**: iCalendar file with warm weather events

**Example**:
```
GET http://localhost:5000/warm.ics
```

##### `GET /cool.ics`

Returns a calendar with cool weather periods (≤72°F and low humidity/dewpoint ≤15.56°C). Events show when it's good to open windows for cooling.

**Response**: iCalendar file with cool weather events

**Example**:
```
GET http://localhost:5000/cool.ics
```

##### `GET /comfort.ics`

Returns a calendar with comfortable weather periods (68-72°F). Events show when it's pleasant to have windows open.

**Response**: iCalendar file with comfortable weather events

**Example**:
```
GET http://localhost:5000/comfort.ics
```

##### `GET /alerts.ics`

Returns a calendar with active weather alerts from the National Weather Service.

**Response**: iCalendar file with weather alert events

**Example**:
```
GET http://localhost:5000/alerts.ics
```

#### Location-Specific Endpoints

##### `GET /<calendar>/<latitude>,<longitude>`

Get a weather calendar for a specific location.

**Parameters**:
- `calendar` (string): Type of calendar - currently only `precip` is supported
- `latitude` (float): Latitude coordinate (-90 to 90)
- `longitude` (float): Longitude coordinate (-180 to 180)

**Response**: iCalendar file for the specified location

**Example**:
```
GET http://localhost:5000/precip/37.7749,-122.4194
```
This returns precipitation forecasts for San Francisco, CA.

**Error Responses**:
- `400 Bad Request`: Invalid latitude or longitude
- `404 Not Found`: Unknown calendar type

### Utility Endpoints

#### `GET /simplify/<latitude>,<longitude>`

Simplifies coordinates to the lowest precision that still returns the same forecast data. This is useful for shortening URLs while maintaining forecast accuracy.

**Parameters**:
- `latitude` (float): Latitude coordinate (-90 to 90)
- `longitude` (float): Longitude coordinate (-180 to 180)

**Response**: JSON object with simplified coordinates

**Example Request**:
```
GET http://localhost:5000/simplify/37.774929,-122.419418
```

**Example Response**:
```json
{
  "latitude": 37.77,
  "longitude": -122.42
}
```

#### `GET /soloize?url=<calendar_url>`

Processes an existing ICS calendar feed by:
1. Removing all past events
2. Removing all attendees from events

This is useful for working around limitations in some calendar applications (like Outlook) that don't properly import Google Calendar feeds with attendees.

**Query Parameters**:
- `url` (string, required): URL of the ICS calendar feed to process

**Response**: Modified iCalendar file

**Example**:
```
GET http://localhost:5000/soloize?url=https://calendar.google.com/calendar/ical/example/basic.ics
```

**Features**:
- Results are cached for fast response times
- Cache is automatically refreshed every 3 hours
- URL validation prevents SSRF attacks
- Only HTTP/HTTPS URLs are allowed
- Localhost and private IP addresses are blocked

**Error Responses**:
- `400 Bad Request`: Missing URL parameter, invalid URL, or malformed ICS feed
- `502 Bad Gateway`: Failed to fetch the source calendar

### Web Interface

#### `GET /`

Returns a simple landing page with information about the service.

**Response**: HTML page

## Event Details

Calendar events include the following information:

- **Name**: Weather condition or event type
- **Time**: Start and end times of the weather condition
- **Description**: Contains:
  - Temperature range (in Fahrenheit)
  - Probability of precipitation range
  - Forecast update timestamp
  - Calendar retrieval timestamp (for cached data)

## Data Source

This service uses the [National Weather Service API](https://www.weather.gov/documentation/services-web-api), which provides free weather data for locations in the United States. No API key is required.

## Caching

- Weather forecasts are cached for performance
- The soloize endpoint caches processed calendars and refreshes them every 3 hours
- Cached responses include timestamps showing when data was retrieved

## Configuration

Default settings can be modified in the source code:

- `MIN_CHANCE_RAIN`: Minimum precipitation probability (33%)
- `MIN_WARM_TEMP`: Minimum temperature for "warm" (68°F)
- `MAX_COOL_TEMP`: Maximum temperature for "cool" (72°F)
- `MAX_COOL_DEWPOINT`: Maximum dewpoint for "cool" (15.56°C)
- `DEFAULT_GRIDPOINT`: Default location for weather data (Mountain View, CA)
- `TIMEZONE_NAME`: Default timezone (America/Los_Angeles)

## Requirements

- Python 3.10+
- Flask
- requests
- ics
- pytz
- cachetools
- gunicorn

See `requirements.txt` for specific versions.

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
