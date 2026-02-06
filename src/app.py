"""
Project OneLight.

Application entry point.
"""

import logging
import sys
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
    session,
)
from quart import abort, jsonify
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
    get_hs100_on_state,
)

from api.device_manager import DeviceManager

from utils import (
    is_get,
    is_post,
    generate_user_id,
    get_secret_key,
    get_app_env,
    signup_workflow,
    login_workflow,
    update_app_config,
    OK_ZERO,
    USERNAME_KEY,
)

from database.database import OneLightDB, DATABASE

from constants import ONELIGHT_LOG_NAME, HOSTING_IP_GLOBAL, HOSTING_IP_LOCAL


KB = 1024
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

logger = logging.getLogger(ONELIGHT_LOG_NAME)
logger.setLevel(logging.DEBUG)

log_fmt = "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
log_handler = RotatingFileHandler("onelight-app.log", maxBytes=80 * KB, backupCount=4)
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
# class Config:
#     DEBUG = False
#     SECRET_KEY = None


# class DevConfig(Config):
#     DEBUG = True
#     ENV = "dev"
#     SECRET_KEY = get_secret_key(ENV)
#     HOST = HOSTING_IP_LOCAL


# class ProdConfig(Config):
#     ENV = "prod"
#     SECRET_KEY = get_secret_key(ENV)
#     HOST = HOSTING_IP_GLOBAL


# Quart app initialization
app = Quart(__name__)

# Fetch env, update app config
env = get_app_env(sys_argv=sys.argv)
update_app_config(app, env)

# app.config.from_object(ProdConfig)
auth_manager = QuartAuth(app)

# Database setup
db = OneLightDB(app, overwrite_if_exists=False)
logger.debug(f"DB config lives at: {app.config.get(DATABASE, '')}")

# Device manager instance (uses new device_manager module)
device_manager = DeviceManager(db)


@app.route("/")
async def index():
    user_is_authenticated = await current_user.is_authenticated
    logger.debug(f"Current user authenticated? {user_is_authenticated}")

    # If already logged in, redirect to home
    if user_is_authenticated:
        return redirect(url_for(HOME))
    # Otherwise show landing page with signup primary and a login option
    return await render_template("landing.html")


@app.route("/signup", methods=METHODS_GET_POST)
async def signup():
    if is_post(request):
        # This statis code represents:
        # - whether signup and account creation/submission
        # - the specific error code if failed
        data = await request.form
        signup_status_code, info = await signup_workflow(data, db)

        if signup_status_code != OK_ZERO:
            await flash(f"Error: {info}. Please try again")
            # return await render_template(SIGNUP_HTML, error=info)
            return redirect(url_for(SIGNUP))
        else:
            await flash(
                f"Successfully registered {data.get(USERNAME_KEY, 'Unknown')}, proceeding to login"
            )
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
            # Bind the authenticated session to the DB user id
            try:
                user_id = int(info)
            except Exception:
                user_id = info
            login_user(AuthUser(str(user_id)))
            logger.info(f"User {user_id} logged in")
            return redirect(url_for(HOME))
        else:
            # If login fail, redirect to login page
            logger.info(info)
            return await render_template(LOGIN_HTML, error=info)

    return await render_template(LOGIN_HTML)  # TODO: Generate a better login page


@app.route("/home")
@login_required
async def home():
    # Render a centered home/dashboard with navigation buttons
    return await render_template("home.html")


@app.route("/logout")
async def logout():
    logout_user()
    return redirect(url_for(INDEX))


@app.route("/devices")
@login_required
async def my_devices():
    # List devices for current user
    try:
        owner_id = int(current_user.auth_id)
    except Exception:
        owner_id = current_user.auth_id
    devices = db.get_devices_for_user(owner_id)
    # Render devices dashboard (template to be created)
    return await render_template("devices.html", devices=devices)


def _ensure_device_owner(device_id: int, owner_id: int):
    device = db.get_device_by_id(device_id)
    if not device:
        abort(404, "Device not found")
    if int(device.get("owner_id")) != int(owner_id):
        abort(403, "Forbidden")
    return device


@app.route("/devices/add")
@login_required
async def add_device_page():
    return await render_template("add_device.html")


@app.route("/devices/scan", methods={GET, POST})
@login_required
async def devices_scan():
    # Trigger network discovery via DeviceManager
    data = None
    try:
        discovered = await device_manager.discover(timeout=5)
        return jsonify({"candidates": discovered})
    except Exception as exc:
        logger.exception("Error during device discovery")
        return jsonify({"error": str(exc)}), 500


@app.route("/devices/register", methods={POST})
@login_required
async def devices_register():
    # Accept JSON body or form data
    payload = await request.get_json(silent=True)
    if not payload:
        form = await request.form
        payload = {k: form.get(k) for k in form.keys()}

    name = payload.get("name") or payload.get("device_name") or "Unnamed Device"
    owner_id = int(current_user.auth_id)
    # discovery_record may be included directly or built from fields
    discovery_record = payload.get("discovery") or {
        "ip": payload.get("ip"),
        "mac": payload.get("mac"),
        "model": payload.get("model"),
    }
    try:
        device_id = await device_manager.provision(discovery_record, owner_id, name)
        if device_id and device_id != -1:
            return jsonify({"device_id": device_id})
        return jsonify({"error": "Provision failed"}), 500
    except Exception as exc:
        logger.exception("Error provisioning device")
        return jsonify({"error": str(exc)}), 500


@app.route("/devices/<int:device_id>")
@login_required
async def device_detail(device_id: int):
    owner_id = int(current_user.auth_id)
    device = _ensure_device_owner(device_id, owner_id)
    return await render_template("device_detail.html", device=device)


@app.route("/devices/<int:device_id>/on", methods={POST})
@login_required
async def device_turn_on(device_id: int):
    owner_id = int(current_user.auth_id)
    _ensure_device_owner(device_id, owner_id)
    try:
        await device_manager.turn_on(device_id)
        return jsonify({"status": "ok"})
    except Exception as exc:
        logger.exception("Error turning device on")
        return jsonify({"error": str(exc)}), 500


@app.route("/devices/<int:device_id>/off", methods={POST})
@login_required
async def device_turn_off(device_id: int):
    owner_id = int(current_user.auth_id)
    _ensure_device_owner(device_id, owner_id)
    try:
        await device_manager.turn_off(device_id)
        return jsonify({"status": "ok"})
    except Exception as exc:
        logger.exception("Error turning device off")
        return jsonify({"error": str(exc)}), 500


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
    app.run(host=app.config.get("HOST", '127.0.0.1'))  # Default to local
