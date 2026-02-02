"""
Project OneLight.

Application entry point.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from markupsafe import escape
from secrets import compare_digest
from typing import Optional

from quart import (
    Blueprint,
    Quart,
    flash,
    get_flashed_messages,
    render_template,
    redirect,
    request,
    url_for,
    session
)
from quart_auth import (
    QuartAuth,
    AuthUser,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from api.smart_device_manager import (
    ping_hs100_device,
    turn_on_hs100,
    turn_off_hs100,
    get_hs100_on_state
)

from utils import (
    is_get,
    is_post,
    generate_user_id,
    signup_workflow,
    login_workflow,
    OK_ZERO
)

from database.database import (
    OneLightDB,
    DATABASE
)


KB = 1024
HOSTING_IP_GLOBAL = "0.0.0.0"
HOSTING_IP_LOCAL = "127.0.0.1"
INDEX_HTML = "index.html"
LOGIN_HTML = "login.html"
SIGNUP_HTML = "signup.html"
INDEX = "index"
LOGIN = "login"
SIGNUP = "signup"
HOME = "home"

POST = "POST"
GET = "GET"
METHODS_GET_POST = {GET, POST}

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


# Add global config classes
class Config:
    DEBUG = False
    SECRET_KEY = "dummy-secret-key"

class DevConfig(Config):
    DEBUG = True

class ProdConfig(Config):
    SECRET_KEY = "IWBcpxkzttNbEI9Tt91xRA"


# Quart app initialization
app = Quart(__name__)
app.config.from_object(DevConfig)
auth_manager = QuartAuth(app)

# Database setup
db = OneLightDB(app, overwrite_if_exists=False)
logger.debug(f"DB config lives at: {app.config.get(DATABASE, '')}")


@app.route("/")
async def index():
    # NEW: force login/signup before accessing any smart plug controls
    return redirect(url_for(SIGNUP))


@app.route("/signup", methods=METHODS_GET_POST)
async def signup():
    if is_post(request):
        # This statis code represents:
        # - whether signup and account creation/submission
        # - the specific error code if failed
        data = await request.form
        signup_status_code, info = await signup_workflow(data, db)

        if signup_status_code != OK_ZERO:
            return await render_template(SIGNUP_HTML, error=info)
        else:
            return redirect(url_for(LOGIN))

    return await render_template(SIGNUP_HTML)

    # Maybe:
    # - make this the default landing page
    # - have a button under the signup fields: "Returning user? [Login here]"


@app.route("/login", methods=METHODS_GET_POST)
async def login():
    if is_post(request):
        data = await request.form

        # TODO: test login logic
        # if data["username"] == "user" and compare_digest(data["password"], "password"):
        #     login_user(AuthUser(generate_user_id()))
        attempted_login_status, info = await login_workflow(data, db)
        if attempted_login_status == 0:
            # If login success, bring customer to home page
            login_user(AuthUser(generate_user_id()))
            logger.info(info)
            return redirect(url_for(HOME))
        else:
            # If login fail, redirect to login page
            logger.info(info)
            return await render_template(LOGIN_HTML, error=info)

    return await render_template(LOGIN_HTML)  # TODO: Generate a better login page


@app.route("/home")
@login_required
async def home():
    # Have the following buttons/options:
    # ===================================
    # [My Devices]
    # [Add New Device]
    # [Logout]

    # For the "My Devices" and "Add New Device" pages, have a "Back" button

    await asyncio.sleep(0)
    return (
        "[PLACEHOLDER] Welcome! You are home.\n"
        f"Your ID: {current_user.auth_id}"

    )

@app.route("/devices")
@login_required
async def my_devices():
    await asyncio.sleep(0)
    return "My devices page."


# WARNING: ROUTES BELOW HERE NEED TO BE REFACTORED SINCE WE ARE
# CONTROLLING DEVICES THROUGH THE DEVICES PAGE...

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
    app.run()
