import datetime
import http.server
import json
import re

import cachetools.func
import ics
import pytz
import requests
from requests import RequestException

SHORT_FORECAST = 'shortForecast'

PORT = 8000
URL = 'https://api.weather.gov/gridpoints/MTR/93,86/forecast/hourly'
ALERT_URL = 'https://api.weather.gov/alerts/active/zone/CAZ508'
MIN_CHANCE_RAIN = 33


def weather_blocks(periods, interest_fn):
    """
    Yields contiguous blocks of events that have similar weather events.

    Args:
        periods (list): A list of periods representing time intervals.
        interest_fn (function): A function that determines whether a period is of interest.

    Yields:
        list: A block of events that have similar weather events.

    """
    current_block = []
    for period in periods:
        of_interest = interest_fn(period)
        rain_interest = (interest_fn == is_rainy)
        forecast = period[SHORT_FORECAST]
        if of_interest:  # this is an hour we'd consider interesting
            # For rainy weather blocks, the shortForecast must match.
            if current_block and (not rain_interest or current_block[0][SHORT_FORECAST] == forecast):
                # we can add this hour to the current block
                current_block.append(period)
            else:
                # we need to start a new block
                if current_block:
                    yield current_block
                current_block = [period]
        else:  # this is no longer an interesting period
            if current_block:
                yield current_block
                current_block = []  # reset
    if current_block:
        yield current_block


def is_rainy(period):
    return period['probabilityOfPrecipitation']['value'] > MIN_CHANCE_RAIN


def is_warm(period):
    return period['temperature'] >= 68


def is_cool(period):
    return period['temperature'] <= 72 and period['dewpoint']['value'] <= 15.5556


def is_comfortable(period):
    return 68 <= period['temperature'] <= 72


def days(periods):
    """
    Groups periods based on their start date and yields a list of periods for each day.

    Args:
        periods (list): A list of periods.

    Yields:
        list: A list of periods for each day.

    Example:
        periods = [
            {'startTime': '2022-01-01T08:00:00', 'isDaytime': True},
            {'startTime': '2022-01-01T12:00:00', 'isDaytime': True},
            {'startTime': '2022-01-02T08:00:00', 'isDaytime': True},
            {'startTime': '2022-01-02T12:00:00', 'isDaytime': True},
            {'startTime': '2022-01-03T08:00:00', 'isDaytime': True},
        ]

        for day in days(periods):
            print(day)

        Output:
        [{'startTime': '2022-01-01T08:00:00', 'isDaytime': True}, {'startTime': '2022-01-01T12:00:00', 'isDaytime': True}]
        [{'startTime': '2022-01-02T08:00:00', 'isDaytime': True}, {'startTime': '2022-01-02T12:00:00', 'isDaytime': True}]
        [{'startTime': '2022-01-03T08:00:00', 'isDaytime': True}]
    """
    current_day = []
    current_date = None
    for period in periods:
        if not period['isDaytime']:
            continue
        start_time = period['startTime']
        this_date: object = start_time.split('T')[0]
        if current_date != this_date:
            if current_day:
                yield current_day
            current_day = [period]
            current_date = this_date
        else:
            current_day.append(period)
    yield current_day


def forecast_desirability(period):
    """
    Derives a sortable desirability key for a given period based on its weather forecast.

    Args:
        period (dict): A dictionary containing weather attributes for a specific period.

    Returns:
        tuple: A tuple containing the calculated values for probability of precipitation,
               temperature discomfort, and wind speed.

    """
    # Treat low probability of rain forecasts as equivalent
    prob_precip = max(period['probabilityOfPrecipitation']['value'], MIN_CHANCE_RAIN)
    temp_discomfort = abs(70 - period['temperature'])
    wind_speed = int(period['windSpeed'].split(' ')[0])
    return prob_precip, temp_discomfort, wind_speed


def format_range(num1, num2):
    """
    Formats a range of numbers as a string.

    Args:
        num1 (int): The starting number of the range.
        num2 (int): The ending number of the range.

    Returns:
        str: The formatted range string.

    Raises:
        None

    Examples:
        >>> format_range(1, 5)
        '1-5'
        >>> format_range(10, 10)
        '10'
    """
    if num1 == num2:
        return str(num1)
    return f"{num1}-{num2}"


def build_rain_calendar(response):
    return build_interesting_weather_calendar(is_rainy, response)


def build_warm_calendar(response):
    return build_interesting_weather_calendar(is_warm, response)


def build_cool_calendar(response):
    return build_interesting_weather_calendar(is_cool, response)


def build_comfort_calendar(response):
    return build_interesting_weather_calendar(is_comfortable, response)


EMOJI_WEATHER = {'Sunny': '☀️',
                 'Mostly Sunny': '🌤',
                 'Partly Sunny': '🌥'}


def build_interesting_weather_calendar(interest_fn, response):
    """
    Builds an interesting weather calendar based on the provided interest function and weather response.

    Args:
        interest_fn (function): The interest function used to determine interesting weather conditions.
        response (object): The HTTP response object.

    Returns:
        ics.Calendar: The calendar containing interesting weather events.
    """
    data = json.loads(response.content)
    forecast_updated = get_forecast_timestamp(data)
    calendar = ics.Calendar()
    for block in weather_blocks(data['properties']['periods'], interest_fn):
        event = ics.Event()
        if interest_fn == is_rainy:
            event.name = block[0]['shortForecast']
        elif interest_fn == is_warm:
            event.name = 'Open 🪟 for ♨️'
        elif interest_fn == is_cool:
            event.name = 'Open 🪟 for 🆒'
        elif interest_fn == is_comfortable:
            event.name = 'Open 🪟'
        event.begin = block[0]['startTime']
        event.end = block[-1]['endTime']
        pops = [period['probabilityOfPrecipitation']['value'] for period in block]
        temps = [period['temperature'] for period in block]
        event.description = f'{format_range(min(temps), max(temps))}F\n' \
                            f'{format_range(min(pops), max(pops))}% chance of rain\n' \
                            f'Forecast updated {forecast_updated}'
        calendar.events.add(event)
    return calendar

TIMEZONE_NAME = 'America/Los_Angeles'

def this_monday():    
    """
    Returns the datetime object representing the start of the current week (Monday at midnight).

    Returns:
        datetime: The datetime object representing the start of the current week.
    """
    # Get the current time
    now = datetime.datetime.now(pytz.timezone(TIMEZONE_NAME))
    
    # Calculate the number of days to subtract to get to the previous Monday
    days_to_subtract = (now.weekday() - 0) % 7
    
    # Subtract the necessary days and set the time to midnight
    monday = now - datetime.timedelta(days=days_to_subtract)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return monday


def get_forecast_timestamp(data):
    """
    Converts the 'updated' timestamp from the given data object to a localized format.

    Args:
        data (dict): The data containing the 'updated' timestamp.

    Returns:
        str: The localized timestamp in the format: 'Wed Apr 03 03:32 PM'.
    """
    updated = data['properties']['updated']
    dt = datetime.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%S%z")
    local_tz = pytz.timezone(TIMEZONE_NAME)  # Replace with your local timezone
    local_dt = dt.astimezone(local_tz)
    forecast_updated = local_dt.strftime("%a %b %d %I:%M %p")
    return forecast_updated


def build_best_weather_calendar(response):
    """
    Builds a calendar object with the best weather forecast events.

    Args:
        response (Response): The response object containing the weather forecast data.

    Returns:
        Calendar: The calendar object with the best weather forecast events.
    """
    data = json.loads(response.content)
    forecast_updated = get_forecast_timestamp(data)
    calendar = ics.Calendar()
    for day in days(data['properties']['periods']):
        best_period = sorted(day, key=forecast_desirability)[0]
        event = ics.Event()
        forecast = best_period['shortForecast']
        temp = best_period['temperature']
        prob_precip = best_period['probabilityOfPrecipitation']['value']

        event.name = forecast
        event.begin = best_period['startTime']
        event.end = best_period['endTime']
        event.description = f'{temp}F, {prob_precip}% chance of rain\nForecast updated {forecast_updated}'
        calendar.events.add(event)
    return calendar


def build_alert_calendar(response) -> ics.Calendar:
    """
    Builds an ics.Calendar object of weather alerts from the given response.

    Args:
        response: The response object containing the data.

    Returns:
        An ics.Calendar object representing the alert calendar.
    """
    data = json.loads(response.content)
    calendar = ics.Calendar()
    for feature in data['features']:
        properties = feature['properties']
        event = ics.Event()
        event.name = properties['event']
        event.begin = properties['onset']
        event.end = properties['ends'] or properties['expires']  # ends
        event.description = re.sub(r'(?<!\n)\n(?!\n)', ' ', properties['description'], 0, re.MULTILINE)
        calendar.events.add(event)
    return calendar


CACHE = cachetools.TTLCache(maxsize=10, ttl=30 * 60)


class Handler(http.server.SimpleHTTPRequestHandler):
    """
    A custom request handler class that extends SimpleHTTPRequestHandler.
    This class handles HTTP requests and provides responses based on the requested path.
    """

    protocol_version = "HTTP/1.1"

    def response(self, status_code, body):
        """
        Sends an HTTP response with the given status code and body.

        Args:
            status_code (int): The HTTP status code.
            body (str): The response body.

        Returns:
            None
        """
        self.send_response(status_code)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        body_str = body.encode('utf-8')
        self.send_header("Content-length", str(len(body_str)))
        self.end_headers()
        self.wfile.write(body_str)
        self.wfile.flush()

    FILTER_PREFIX = '/filter?'
    def do_GET(self):
            """
            Handles GET requests.

            This method is responsible for handling different GET requests based on the path.
            It checks the path and performs the corresponding action based on the path value.
            If the path is '/', it returns a greeting message with the port number.
            If the path is '/weather.ics', it requests the rain calendar.
            If the path is '/alerts.ics', it requests the alerts calendar.
            If the path is '/bestweather.ics', it requests the best weather calendar.
            If the path is '/warm.ics', it requests the warm weather calendar.
            If the path is '/cool.ics', it requests the cool weather calendar.
            If the path is '/comfort.ics', it requests the comfortable weather calendar.
            If the path starts with the FILTER_PREFIX, it filters the large ics feed based on the feed URL.
            If none of the above conditions match, it returns a 404 response with a message.

            Returns:
                None
            """
            if self.path == '/':
                self.response(200, f'Hello world, on port {PORT}!')
            
            if self.path == "/weather.ics":
                print('Requesting rain')
                self.try_nws_calendar(URL, build_rain_calendar)
            elif self.path == '/alerts.ics':
                print('Requesting alerts')
                self.try_nws_calendar(ALERT_URL, build_alert_calendar)
            elif self.path == '/bestweather.ics':
                print('Requesting weather')
                self.try_nws_calendar(URL, build_best_weather_calendar)
            elif self.path == '/warm.ics':
                print('Requesting warm weather')
                self.try_nws_calendar(URL, build_warm_calendar)
            elif self.path == '/cool.ics':
                print('Requesting cool weather')
                self.try_nws_calendar(URL, build_cool_calendar)
            elif self.path == '/comfort.ics':
                print('Requesting comfortable weather')
                self.try_nws_calendar(URL, build_comfort_calendar)
            elif self.path.startswith(Handler.FILTER_PREFIX):
                feed_url = self.path[len(Handler.FILTER_PREFIX):]
                print('Filtering large ics feed:', feed_url)
                self.filter_ics(feed_url)
            else:
                print('Sending 404')
                self.response(404, 'Sad trombone: nothing found.')
            self.close_connection = True
            print(fetch_url.cache_info())

    def filter_ics(self, feed_url):
        """
        Filters an ics feed to return events starting from Monday of this week.

        Args:
            feed_url (str): The URL of the feed to filter.

        Returns:
            None
        """
        try:
            response = fetch_url(feed_url)
            calendar = ics.Calendar(str(response.text))
            filtered = ics.Calendar()
            # start_after only returns events strictly after a timestamp, so we need to subtract a microsecond
            threshold = this_monday() - datetime.timedelta(microseconds=1)
            for event in calendar.timeline.start_after(threshold):
                filtered.events.add(event)
            print(f'Filtered from {len(calendar)} to {len(filtered)} events.')
            self.response(200, filtered.serialize())
        except RequestException as err:
            print('Error:', err)
            response = err.response
            self.response(response.status_code, response.text)
    
    def try_nws_calendar(self, url, calendar_builder):
        """
        Tries to fetch a calendar from the given URL and build it using the provided calendar builder.

        Args:
            url (str): The URL to fetch the calendar from.
            calendar_builder (function): The function to build the calendar.

        Returns:
            None
        """
        try:
            response = fetch_url(url)
            calendar = calendar_builder(response)
            self.response(200, calendar.serialize())
        except RequestException as err:
            print('Error:', err)
            response = err.response
            self.response(response.status_code, response.text)

    def close_connection(self):
        """
        Closes the connection.

        Returns:
            None
        """
        self.wfile.flush()
        self.rfile.close()
        self.connection.close()


@cachetools.cached(cache=CACHE, info=True)
def fetch_url(url):
    """
    Fetches the content of the specified URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        requests.Response: The response object containing the fetched content.

    Raises:
        requests.HTTPError: If the response status code is not 200.
    """
    print('Fetching', url)
    response = requests.get(url)
    if response.status_code != 200:
        response.raise_for_status()
    return response


with http.server.ThreadingHTTPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print('Server stopped.')