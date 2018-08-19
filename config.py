import os
import configparser

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
    db_sfx = config.get('MYSQL', 'database_sfx')


    SECRET_KEY = os.environ.get('SECRET_KEY') or secret

    DISCORD_OAUTH_CLIENT_ID = os.environ.get('DISCORD_OAUTH_CLIENT_ID') or client_id
    DISCORD_OAUTH_CLIENT_SECRET = os.environ.get('DISCORD_OAUTH_CLIENT_SECRET') or client_secret

    BOT_TOKEN = token

    if passwd is not None:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8mb4'.format(user=user, password=passwd, host=host, db=db)
        SQLALCHEMY_BINDS = {
            'soundfx': 'mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8mb4'.format(user=user, password=passwd, host=host, db=db_sfx)
        }
    else:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{user}@{host}/{db}?charset=utf8mb4'.format(user=user, host=host, db=db)
        SQLALCHEMY_BINDS = {
            'soundfx': 'mysql+pymysql://{user}@{host}/{db}?charset=utf8mb4'.format(user=user, host=host, db=db_sfx)
        }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
