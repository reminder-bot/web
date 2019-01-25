import os
import configparser
from datetime import datetime


def produce_offset(timezone):
    hours = pytz.timezone(timezone).utcoffset(datetime.now()).total_seconds() / 3600

    if int(hours) == float(hours):
        if hours < 0:
            return '{}'.format(int(hours))
        else:
            return '+{}'.format(int(hours))

    else:
        if hours < 0:
            hour = int(hours)
            minute = str(int(abs(60 * (hours - hour))))

            return '{}:{}'.format(hour, minute)

        else:
            hour = int(hours)
            minute = str(int(60 * (hours - hour)))

            return '+{}:{}'.format(hour, minute)


class Config(object):
    BASE_URI = './'

    config = configparser.SafeConfigParser()
    config.read(BASE_URI + 'config.ini')
    client_id = config.get('WEB', 'DISCORD_OAUTH_CLIENT_ID')
    client_secret = config.get('WEB', 'DISCORD_OAUTH_CLIENT_SECRET')
    secret = config.get('WEB', 'SECRET')

    token = config.get('DEFAULT', 'token')

    user = config.get('MYSQL', 'user')
    try:
        passwd = config.get('MYSQL', 'passwd')
    except:
        passwd = None
    host = config.get('MYSQL', 'host')
    db = config.get('MYSQL', 'database')

    SECRET_KEY = os.environ.get('SECRET_KEY') or secret

    DISCORD_OAUTH_CLIENT_ID = os.environ.get('DISCORD_OAUTH_CLIENT_ID') or client_id
    DISCORD_OAUTH_CLIENT_SECRET = os.environ.get('DISCORD_OAUTH_CLIENT_SECRET') or client_secret

    BOT_TOKEN = token

    SESSION_TYPE = 'sqlalchemy'

    if passwd is not None:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8mb4'.format(user=user, password=passwd, host=host, db=db)
    else:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{user}@{host}/{db}?charset=utf8mb4'.format(user=user, host=host, db=db)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PATREON_ROLES = [353630811561394206, 353226278435946496]
