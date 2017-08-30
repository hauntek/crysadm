from flask import Flask
import config, socket, redis
import uuid
from datetime import timedelta

app = Flask(__name__)

"""
if socket.gethostname() == 'GXMBP.local':
    app.config.from_object(config.DevelopmentConfig)
elif socket.gethostname() == 'iZ23bo17lpkZ':
    app.config.from_object(config.ProductionConfig)
else:
    app.config.from_object(config.TestingConfig)
"""

app.config.from_object(config.ProductionConfig)
redis_conf = app.config.get('REDIS_CONF')
pool = redis.ConnectionPool(host=redis_conf.host, port=redis_conf.port, db=redis_conf.db, password=redis_conf.password)
r_session = redis.Redis(connection_pool=pool)

from admin import *
from user import *
from web_common import *
from account import *
from excavator import *
from message import *
from analyzer import *
from update import *
from console import *

if __name__ == '__main__':
    app.secret_key = str(uuid.uuid1())
    app.permanent_session_lifetime = timedelta(minutes=120)
    app.run(host=app.config.get('SERVER_IP'), port=app.config.get('SERVER_PORT'))
