from flask import Flask
from config import Config
from flask_dance.contrib.discord import make_discord_blueprint, discord
from flask_sqlalchemy import SQLAlchemy


def to_hex(i):
    return hex(i)[2:]


app = Flask(__name__)
app.config.from_object(Config)
app.jinja_env.globals.update(hex=to_hex)
discord_blueprint = make_discord_blueprint(scope=['identify', 'guilds'], redirect_url='cache')
app.register_blueprint(discord_blueprint, url_prefix='/login')
db = SQLAlchemy(app)

from app import routes, models

db.create_all()
