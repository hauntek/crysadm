__author__ = 'powergx'
import hashlib
from flask import session

def hash_password(pwd):
    """
        :param pwd: input password
        :return: return hash md5 password
        """
    from crysadm import app

    return hashlib.md5(str("%s%s" % (app.config.get("PASSWORD_PREFIX"), pwd)).encode('utf-8')).hexdigest()

def md5(s):
    import hashlib

    return hashlib.md5(s.encode('utf-8')).hexdigest().lower()

def sha1(s):
    import hashlib

    return hashlib.sha1(s.encode('utf-8')).hexdigest().lower()

def get_message():
    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None
    return err_msg

def set_message(message,type='error'):
    if type == 'error':
        session['error_message'] = message
    elif type == 'info':
        session['info_message'] = message