from app import db

class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column( db.Integer, primary_key=True, unique=True )
    hashpack = db.Column( db.String(64), unique=True )
    message = db.Column( db.String(2000) )
    channel = db.Column( db.BigInteger )
    time = db.Column( db.BigInteger )
    position = db.Column( db.Integer )

    webhook = db.Column( db.String(256) )
    avatar = db.Column( db.String(512), default="https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg", nullable=False )
    username = db.Column( db.String(32), default="Reminder", nullable=False )

    method = db.Column( db.Text )
    embed = db.Column( db.Integer, nullable=True )

    intervals = db.relationship('Interval', backref='r', lazy='dynamic')

    channel_name = 'unknown'


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
    language = db.Column( db.String(2), default="EN", nullable=False )
    timezone = db.Column( db.String(30), default="UTC", nullable=False )


# CACHING MODELS
guild_members = db.Table('guild_members',
    db.Column('guild', db.BigInteger, db.ForeignKey('guild_cache.guild')),
    db.Column('member', db.BigInteger, db.ForeignKey('member_cache.member')),
    db.Column('permissions', db.Boolean),
)

class Member(db.Model):
    __tablename__ = 'member_cache'

    id = db.Column( db.Integer, primary_key=True )
    member = db.Column( db.BigInteger, unique=True )

    patreon = db.Column( db.Integer )
    name = db.Column( db.Text )

    cache_time = db.Column( db.Integer )


class GuildData(db.Model):
    __tablename__ = 'guild_cache'

    id = db.Column( db.Integer, primary_key=True )
    guild = db.Column( db.BigInteger, unique=True )

    name = db.Column( db.Text )
    channels = db.relationship('ChannelData', backref='g', lazy='dynamic')
    members = db.relationship(
        'Member', secondary=guild_members,
        primaryjoin=(guild_members.c.guild == guild),
        secondaryjoin=(guild_members.c.member == Member.member),
        backref=db.backref('guilds', lazy='dynamic'), lazy='dynamic'
        )

    cache_time = db.Column( db.Integer )


class ChannelData(db.Model):
    __tablename__ = 'channel_cache'

    id = db.Column( db.Integer, primary_key=True )
    channel = db.Column( db.BigInteger, unique=True )
    guild = db.Column( db.BigInteger, db.ForeignKey('guild_cache.guild') )

    name = db.Column( db.Text )
