from app import db
import secrets
from sqlalchemy.dialects.mysql import BIGINT


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.BigInteger, unique=True)

    patreon = db.Column(db.Boolean, nullable=False, default=False)
    dm_channel = db.Column(db.BigInteger)
    name = db.Column(db.String(64))


class Embed(db.Model):
    __tablename__ = 'embeds'

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(256), nullable=False, default='')
    description = db.Column(db.String(2048), nullable=False, default='')
    color = db.Column(db.Integer, nullable=False, default=0x0)


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)

    content = db.Column(db.String(2048), nullable=False, default='')
    embed_id = db.Column(db.Integer, db.ForeignKey(Embed.id))
    embed = db.relationship(Embed)

    # determines if this should be deleted when the reminder goes off or not
    on_demand = db.Column(db.Boolean, nullable=False, default=True)

    owner_id = db.Column(db.Integer, db.ForeignKey(User.id))


class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column(db.Integer, primary_key=True, unique=True)
    uid = db.Column(db.String(64), unique=True, default=lambda: Reminder.create_uid())

    message_id = db.Column(db.Integer, db.ForeignKey(Message.id), nullable=False)
    message = db.relationship(Message)

    channel = db.Column(db.BigInteger)
    time = db.Column(db.BigInteger)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    webhook = db.Column(db.String(256))
    avatar = db.Column(db.String(512),
                       default='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg',
                       nullable=False)
    username = db.Column(db.String(32), default='Reminder', nullable=False)

    method = db.Column(db.String(9))

    interval = db.Column(db.Integer)

    channel_name = 'unknown'

    @staticmethod
    def create_uid():
        full: str = ''
        while len(full) < 64:
            full += secrets.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')

        return full

    def hex_color(self):
        if self.message.embed is None:
            return

        else:
            return hex(self.message.embed.color)[2:]


class Guild(db.Model):
    __tablename__ = 'guilds'

    guild = db.Column(db.BigInteger, primary_key=True, autoincrement=False)
    prefix = db.Column(db.String(5), default="$", nullable=False)
    timezone = db.Column(db.String(30), default="UTC", nullable=False)


# CACHING MODELS
guild_users = db.Table('guild_users',
                       db.Column('guild', db.BigInteger, db.ForeignKey('guild_cache.guild')),
                       db.Column('user', BIGINT(unsigned=True), db.ForeignKey('users.user')),
                       )

guild_partials = db.Table('guild_partials',
                          db.Column('guild', db.BigInteger, db.ForeignKey('guild_cache.guild')),
                          db.Column('user', db.BigInteger, db.ForeignKey('partial_cache.user')),
                          )


class PartialMember(db.Model):
    __tablename__ = 'partial_cache'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.BigInteger, unique=True)
    name = db.Column(db.String(64))


class GuildData(db.Model):
    __tablename__ = 'guild_cache'

    id = db.Column(db.Integer, primary_key=True)
    guild = db.Column(db.BigInteger, unique=True)

    name = db.Column(db.Text)

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

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.BigInteger, unique=True)
    guild = db.Column(db.BigInteger, db.ForeignKey('guild_cache.guild'))

    name = db.Column(db.Text)


class ChannelData(db.Model):
    __tablename__ = 'channel_cache'

    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.BigInteger, unique=True)
    guild = db.Column(db.BigInteger, db.ForeignKey('guild_cache.guild'))

    name = db.Column(db.Text)
