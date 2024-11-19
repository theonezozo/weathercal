"""
This module defines a Flask web application with several routes for generating weather-related calendar files.
Routes:
    /: Renders the index page.
    /weather.ics: Returns a calendar file with rain forecasts.
    /alerts.ics: Returns a calendar file with weather alerts.
    /bestweather.ics: Returns a calendar file with the best weather forecasts.
    /warm.ics: Returns a calendar file with warm weather forecasts.
    /cool.ics: Returns a calendar file with cool weather forecasts.
    /comfort.ics: Returns a calendar file with comfortable weather forecasts.
Functions:
    index(): Handles requests to the index page.
    weather(): Handles requests for the rain calendar.
    alerts(): Handles requests for the alerts calendar.
    best_weather(): Handles requests for the best weather calendar.
    warm(): Handles requests for the warm weather calendar.
    cool(): Handles requests for the cool weather calendar.
    comfort(): Handles requests for the comfortable weather calendar.

"""

import flask
import nws

app = flask.Flask(__name__)

ICS_CONTENT_TYPE = "text/calendar"
DEBUG = True
CAL_CONTENT_TYPE = "text/plain" if DEBUG else ICS_CONTENT_TYPE


@app.route("/")
def index() -> str:
    """
    Handle the request for the index page.

    This function logs a message indicating that a request for the index page
    has been received and returns the rendered HTML template for the index page.

    Returns:
        str: The rendered HTML content for the index page.
    """
    print("Request for index page received")
    return flask.render_template("index.html")


@app.route("/weather.ics")
def weather() -> str:
    print("Requesting rain calendar")
    return flask.Response(
        nws.get_rain_calendar(),
        content_type=CAL_CONTENT_TYPE,
    )


@app.route("/alerts.ics")
def alerts() -> str:
    print("Requesting alerts")
    return flask.Response(nws.get_alert_calendar(), content_type=CAL_CONTENT_TYPE)


@app.route("/bestweather.ics")
def best_weather() -> str:
    print("Requesting best weather")
    return flask.Response(
        nws.get_best_weather_calendar(), content_type=CAL_CONTENT_TYPE
    )


@app.route("/warm.ics")
def warm() -> str:
    print("Requesting warm weather")
    return flask.Response(nws.get_warm_calendar(), content_type=CAL_CONTENT_TYPE)


@app.route("/cool.ics")
def cool() -> str:
    print("Requesting cool weather")
    return flask.Response(nws.get_cool_calendar(), content_type=CAL_CONTENT_TYPE)


@app.route("/comfort.ics")
def comfort() -> str:
    print("Requesting comfortable weather")
    return flask.Response(nws.get_comfort_calendar(), content_type=CAL_CONTENT_TYPE)


if __name__ == "__main__":
    app.run()
