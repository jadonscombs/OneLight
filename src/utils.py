"""
Docstring for src.utils
"""

import configparser
import logging
import re
import string
import uuid
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Tuple

import bcrypt
from quart import Request

from database.database import OneLightDB

from constants import SECRETS_CONFIG_FILE


logger = logging.getLogger("onelight-app")


GET = "GET"
POST = "POST"
UTF8 = "utf-8"
USERNAME_KEY = "username"
EMAIL_KEY = "email"
PASSWORD_KEY = "password"

PASSWORD_MIN_LENGTH = 8

OK_ZERO = 0


# Status codes specifically for <is_valid_form_fields()>
class FormValidationCodes(Enum):
    """
    Code US: Username validation failure
    Code EM: Email validation failure
    Code PW: Password validation error
    """

    US = 1
    EM = auto()
    PW = auto()
    UAC = auto()


def is_post(request: Request):
    return request.method == POST


def is_get(request: Request):
    return request.method == GET


def generate_user_id() -> str:
    return str(uuid.uuid4())


def is_valid_password(password: str) -> int:
    # check that password meets all password requirements:
    # - password not missing/empty
    # - password longer than 7 characters
    # - password has at least 1 uppercase letter
    # - password has at least 1 lowercase letter
    # - password contains at least 1 special character
    # - password has at least 1 number
    #
    # Error codes are as follows:
    # -1: password empty
    # -2: password length fail
    # -3: password uppercase requirement fail
    # -4: password lowercase requirement fail
    # -5: password special character fail
    # -6: password number requirement
    if not password:
        return -1
    if len(password) < PASSWORD_MIN_LENGTH:
        return -2
    if not re.search(r"[A-Z]", password):
        return -3
    if not re.search(r"[a-z]", password):
        return -4
    if not re.search(f"[{re.escape(string.punctuation)}]", password):
        return -5
    if not re.search(r"[0-9]", password):
        return -6
    return OK_ZERO


def is_valid_username(username: str, db: OneLightDB) -> int:
    # - check that username is not taken or missing
    #   -> fail with code -1
    if not username:
        return -1
    if db.username_in_use(username):
        return -2
    return OK_ZERO


def is_valid_email(email: str, db: OneLightDB) -> int:
    # - check that email is not in use or missing
    #   -> fail with code -2
    if not email:
        return -1
    if db.email_in_use(email):
        return -2
    return OK_ZERO


def is_valid_form_fields(request_form: Any, db: OneLightDB) -> Tuple:
    res: Optional[int] = None
    try:
        username: str = request_form.get(USERNAME_KEY)
        res = is_valid_username(username, db)
        assert res == OK_ZERO
    except Exception:
        logger.exception(f"Username validation failed (code {res})")
        return (FormValidationCodes.US.value, FormValidationCodes.US.name)
    try:
        email: str = request_form.get(EMAIL_KEY)
        res = is_valid_email(email, db)
        assert res == OK_ZERO
    except Exception:
        logger.exception(f"Email validation failed (code {res})")
        return (FormValidationCodes.EM.value, FormValidationCodes.EM.name)
    try:
        password: str = request_form.get(PASSWORD_KEY)
        res = is_valid_password(password)
        assert res == OK_ZERO
    except Exception:
        logger.exception(f"Password validation failed (code {res})")
        return (FormValidationCodes.PW.value, FormValidationCodes.PW.name)

    logger.info("[OK] Signup form validation complete")
    return (OK_ZERO, "OK")


def hash_signup_password(password: str) -> str:
    password_bytes: bytes = password.encode(encoding=UTF8)
    hashed_bytes: bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    hashed_str: str = hashed_bytes.decode("utf-8")
    return hashed_str


def verify_login_password(password: str, stored_hash: str) -> bool:
    password_bytes: bytes = password.encode(encoding=UTF8)
    stored_hash_bytes: bytes = stored_hash.encode(encoding=UTF8)
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)


async def signup_workflow(request_form: Any, db: OneLightDB) -> Tuple:
    """
    Run the customer signup workflow - return code 0 on success
    """
    fields_valid_status, status_name = is_valid_form_fields(request_form, db)
    logger.debug(
        {
            "operation": "validate_signup_form",
            "status": fields_valid_status,
            "status_name": status_name,
        }
    )

    # If signup form validation failed...abort signup and return status code
    if fields_valid_status != OK_ZERO:
        logger.error("signup_workflow(): form field validation failed.")
        return (fields_valid_status, "Invalid username, password or email")

    # Continue registration - Make DB entries for user account
    add_account_status_code = db.add_user_account(
        request_form.get(USERNAME_KEY),
        request_form.get(EMAIL_KEY),
        hash_signup_password(request_form.get(PASSWORD_KEY)),
    )
    status_name = FormValidationCodes.UAC.name
    logger.debug(
        {
            "operation": "add_new_account",
            "status": add_account_status_code,
            "status_name": status_name,
        }
    )

    # If new account addition fails...abort signup and return status code.
    # TODO: At this point, will need to clean up "users" DB and remove traces
    # of the new account
    if add_account_status_code != OK_ZERO:
        logger.error(
            "OneLightDB.add_user_account(): status code indicates failure. "
            "Please review application logs for more detail."
        )
        return (add_account_status_code, "AddAccountError")

    return (OK_ZERO, "AddAccountOK")


async def login_workflow(request_form: Any, db: OneLightDB) -> Tuple:
    """
    Run the customer login workflow - return code 0 on success
    """

    username: str = request_form.get(USERNAME_KEY)
    password: str = request_form.get(PASSWORD_KEY)

    # Steps:
    #
    # - check that the username exists in the DB
    # - check that the password matches the hashed password associated with
    #   this customer's record
    #
    # - If either condition fails, send a message indicating either field
    #   is invalid, but do not indicate which one exactly
    is_existing_username: bool = db.username_in_use(username)
    stored_password_hash: Optional[str] = db.fetch_password_hash_for_username(username)
    is_matching_password: bool = False
    if not stored_password_hash:
        logger.error(f"Password hash for '{username}' could not be found...")
    else:
        is_matching_password: bool = verify_login_password(
            password, stored_password_hash
        )

    login_fail_message: str = "Invalid username or password, please try again."
    if not is_existing_username or not is_matching_password:
        return (-1, login_fail_message)
    # Fetch the user's DB record so the caller can bind session to user id
    user_record = db.fetch_user_by_username(username)
    if not user_record:
        return (-1, login_fail_message)

    return (0, user_record.get("id"))


# Config helper
def get_secret_key(env: str):
    try:
        assert env in ("dev", "prod")
    except AssertionError:
        logger.error(f"Invalid application environment ('{env}')")
        return None

    config_path = Path(SECRETS_CONFIG_FILE).resolve()
    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        key = config["SECRETS"][f"{env}_secret_key"]
        logger.debug(f"Is secret key None? {key is None}")
        return key
    except Exception:
        logger.exception(
            f"Exception returning secret key for env '{env}'. Returning None"
        )
        return None


# Config helper
def get_app_env():
    config_path = Path(SECRETS_CONFIG_FILE)
    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        return config["CONFIG"]["env"]
    except Exception:
        logger.exception(
            f"Exception returning env param from '{SECRETS_CONFIG_FILE}' file"
        )
        raise
