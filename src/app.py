"""
Project OneLight.

Application entry point.
"""

from flask import Flask
from markupsafe import escape


app = Flask(__name__)

@app.route("/")
def index():
    # TODO: Return a basic HTML page with two clickable buttons:
    # - button 1: "ON"
    # - button 2: "OFF"
    return 'Index page. Nothing to see here...'

@app.route("/on")
def turn_on():
    return "Light turned on!"

@app.route("/off")
def turn_off():
    return "Light turned off!"


# Development -- make safer adjustments later
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=3000, debug=True)