from P4 import P4, P4Exception

p4 = P4()

from .functions import *


class P4PasswordException(P4Exception):
    pass


def disconnect():
    if p4.connected():
        p4.disconnect()


def init(username=None, port=None, password=None):
    if port and p4.port != port:
        disconnect()
        p4.port = port or p4.port
    p4.user = username or p4.user
    if not p4.connected():
        p4.connect()
    try:
        p4.run_login("-s")
    except P4Exception as e:
        if not password:
            raise e
        # If not logged in already, try with the password.
        p4.password = password
        try:
            p4.run_login()
        except P4Exception as e:
            if "invalid or unset" in e.errors[0]:
                raise e
    return True
