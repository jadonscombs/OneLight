"""
Project OneLight.

Application entry point.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler

from quart import Quart, render_template
from markupsafe import escape

from api.smart_device_manager import (
    ping_hs100_device,
    turn_on_hs100,
    turn_off_hs100,
    get_hs100_on_state
)


KB = 1024
HOSTING_IP_GLOBAL = "0.0.0.0"
HOSTING_IP_LOCAL = "127.0.0.1"
INDEX = "index.html"

logger = logging.getLogger("onelight-app")
logger.setLevel(logging.DEBUG)

log_fmt = '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
log_handler = RotatingFileHandler(
    "onelight-app.log",
    maxBytes=80*KB,
    backupCount=4
)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(logging.Formatter(log_fmt))

# Console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(log_fmt))

# Add log handlers
logger.addHandler(log_handler)
logger.addHandler(console_handler)

app = Quart(__name__)


@app.route("/")
async def index():
    return await render_template(INDEX)


@app.route("/on")
async def turn_on():
    await turn_on_hs100()
    return "Light turned on!"


@app.route("/off")
async def turn_off():
    await turn_off_hs100()
    return "Light turned off!"


@app.route("/hs100_status")
async def hs100_status():
    return await ping_hs100_device()


@app.route("/hs100_state")
async def hs100_state():
    return await get_hs100_on_state()


# Development -- make safer adjustments later
if __name__ == "__main__":
    app.run(host=HOSTING_IP_GLOBAL, port=3000, debug=False)
