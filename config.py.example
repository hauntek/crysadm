__author__ = 'powergx'


class RedisConfig():
    def __init__(self, host, port, db, password=None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password


class Config(object):
    DEBUG = False
    TESTING = False
    DATABASE_URI = ''
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    SESSION_TYPE = 'memcached'
    SECRET_KEY = '7e30485a-dd01-11e4-8abd-10ddb199c373'
    REDIS_CONF = RedisConfig(host='127.0.0.1', port=6379, db=0)
    PASSWORD_PREFIX = "08b3db21-d120-11e4-9ttd-10ddb199c373"
    ENCRYPT_PWD_URL = None
    SERVER_IP = '0.0.0.0'
    SERVER_PORT = 5000


class ProductionConfig(Config):
    DEBUG = True


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
