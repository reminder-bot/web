from app import db
import secrets

class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column( db.Integer, primary_key=True, unique=True )
    uid = db.Column( db.String(64), unique=True, default=lambda: Reminder.create_uid() )

    message = db.Column( db.String(2000) )
    channel = db.Column( db.BigInteger )
    time = db.Column( db.BigInteger )
    position = db.Column( db.Integer )
    enabled = db.Column( db.Boolean, nullable=False, default=True )

    webhook = db.Column( db.String(256) )
    avatar = db.Column( db.String(512), default="https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg", nullable=False )
    username = db.Column( db.String(32), default="Reminder", nullable=False )

    method = db.Column( db.Text )
    embed = db.Column( db.Integer, nullable=True )

    intervals = db.relationship('Interval', backref='r', lazy='dynamic')

    channel_name = 'unknown'

    @staticmethod
    def create_uid():
        full = ""
        while len(full) < 64:
            full += secrets.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')

        return full


class Interval(db.Model):
    __tablename__ = 'intervals'

    id = db.Column( db.Integer, primary_key=True, unique=True)

    reminder = db.Column(db.Integer, db.ForeignKey('reminders.id'))

    period = db.Column(db.Integer)
    position = db.Column(db.Integer)


class Server(db.Model):
    __tablename__ = 'servers'

    id = db.Column( db.Integer, primary_key=True )
    server = db.Column( db.BigInteger, unique=True )
    prefix = db.Column( db.String(5), default="$", nullable=False )
    timezone = db.Column( db.String(30), default="UTC", nullable=False )


# CACHING MODELS
guild_users = db.Table('guild_users',
    db.Column('guild', db.BigInteger, db.ForeignKey('guild_cache.guild')),
    db.Column('user', db.BigInteger, db.ForeignKey('user_cache.user')),
)

guild_partials = db.Table('guild_partials',
    db.Column('guild', db.BigInteger, db.ForeignKey('guild_cache.guild')),
    db.Column('user', db.BigInteger, db.ForeignKey('partial_cache.user')),
)

class User(db.Model):
    __tablename__ = 'user_cache'

    id = db.Column( db.Integer, primary_key=True )
    user = db.Column( db.BigInteger, unique=True )

    patreon = db.Column( db.Integer )
    dm_channel = db.Column( db.BigInteger )
    name = db.Column( db.String(64) )


class PartialMember(db.Model):
    __tablename__ = 'partial_cache'

    id = db.Column( db.Integer, primary_key=True )
    user = db.Column( db.BigInteger, unique=True )
    name = db.Column( db.String(64) )


class GuildData(db.Model):
    __tablename__ = 'guild_cache'

    id = db.Column( db.Integer, primary_key=True )
    guild = db.Column( db.BigInteger, unique=True )

    name = db.Column( db.Text )

    channels = db.relationship('ChannelData', backref='g', lazy='dynamic')
    roles = db.relationship('RoleData', backref='g', lazy='dynamic')

    users = db.relationship(
        'User', secondary=guild_users,
        primaryjoin=(guild_users.c.guild == guild),
        secondaryjoin=(guild_users.c.user == User.user),
        backref=db.backref('guilds', lazy='dynamic'), lazy='dynamic'
    )
    partials = db.relationship(
        'PartialMember', secondary=guild_partials,
        primaryjoin=(guild_partials.c.guild == guild),
        secondaryjoin=(guild_partials.c.user == PartialMember.user),
        backref=db.backref('guild', lazy='dynamic'), lazy='dynamic'
    )


class RoleData(db.Model):
    __tablename__ = 'role_cache'

    id = db.Column( db.Integer, primary_key=True )
    role = db.Column( db.BigInteger, unique=True )
    guild = db.Column( db.BigInteger, db.ForeignKey('guild_cache.guild') )

    name = db.Column( db.Text )


class ChannelData(db.Model):
    __tablename__ = 'channel_cache'

    id = db.Column( db.Integer, primary_key=True )
    channel = db.Column( db.BigInteger, unique=True )
    guild = db.Column( db.BigInteger, db.ForeignKey('guild_cache.guild') )

    name = db.Column( db.Text )
