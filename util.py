__author__ = 'powergx'

def hash_password(pwd):
    import hashlib
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
