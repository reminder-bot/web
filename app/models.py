from app import db
import secrets
from sqlalchemy.dialects.mysql import BIGINT, MEDIUMINT, INTEGER as INT


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(INT(unsigned=True), primary_key=True)
    user = db.Column(BIGINT(unsigned=True), unique=True)

    patreon = db.Column(db.Boolean, nullable=False, default=False)
    dm_channel = db.Column(BIGINT(unsigned=True))
    language = db.Column(db.String(2), nullable=False, default='EN')
    name = db.Column(db.String(37))


class Embed(db.Model):
    __tablename__ = 'embeds'

    id = db.Column(INT(unsigned=True), primary_key=True)

    title = db.Column(db.String(256), nullable=False, default='')
    description = db.Column(db.String(2048), nullable=False, default='')
    color = db.Column(MEDIUMINT(unsigned=True), nullable=False, default=0x0)


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(INT(unsigned=True), primary_key=True)

    content = db.Column(db.String(2048), nullable=False, default='')
    embed_id = db.Column(INT(unsigned=True), db.ForeignKey(Embed.id))
    embed = db.relationship(Embed)


guild_users = db.Table('guild_users',
                       db.Column('guild', INT(unsigned=True), db.ForeignKey('guilds.id')),
                       db.Column('user', INT(unsigned=True), db.ForeignKey('users.id')),
                       )


class Guild(db.Model):
    __tablename__ = 'guilds'

    id = db.Column(INT(unsigned=True), primary_key=True)
    guild = db.Column(BIGINT(unsigned=True), unique=True)
    name = db.Column(db.String(100))

    prefix = db.Column(db.String(5), default="$", nullable=False)
    timezone = db.Column(db.String(30), default="UTC", nullable=False)

    channels = db.relationship('Channel', backref='guild', lazy='dynamic')
    roles = db.relationship('Role', backref='guild', lazy='dynamic')

    users = db.relationship(
        'User', secondary=guild_users,
        primaryjoin=(guild_users.c.guild == id),
        secondaryjoin=(guild_users.c.user == User.id),
        backref=db.backref('guilds', lazy='dynamic'), lazy='dynamic'
    )


class Channel(db.Model):
    __tablename__ = 'channels'

    id = db.Column(INT(unsigned=True), primary_key=True)
    channel = db.Column(BIGINT(unsigned=True), unique=True)
    name = db.Column(db.String(100))

    webhook_id = db.Column(BIGINT(unsigned=True), unique=True)
    webhook_token = db.Column(db.Text)

    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id, ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return '{}.{}'.format(self.name, self.channel)

    def update_webhook(self, api_get, api_post, client_id):
        # get existing webhooks
        webhooks = api_get('channels/{}/webhooks'.format(self.channel)).json()

        if isinstance(webhooks, list):
            existing = [x for x in webhooks if x['user']['id'] == client_id]

            if len(existing) == 0:
                # get new webhook
                req = api_post('channels/{}/webhooks'.format(self.channel), {'name': 'Reminders'}).json()
                self.webhook_id = req['id']
                self.webhook_token = req['token']

            else:
                self.webhook_id = existing[0]['id']
                self.webhook_token = existing[0]['token']


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(INT(unsigned=True), primary_key=True)
    role = db.Column(BIGINT(unsigned=True), unique=True, nullable=False)
    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id), nullable=False)

    name = db.Column(db.String(100))


class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column(INT(unsigned=True), primary_key=True, unique=True)
    uid = db.Column(db.String(64), unique=True, default=lambda: Reminder.create_uid())

    message_id = db.Column(INT(unsigned=True), db.ForeignKey(Message.id), nullable=False)
    message = db.relationship(Message)

    channel_id = db.Column(INT(unsigned=True), db.ForeignKey(Channel.id), nullable=True)
    channel = db.relationship(Channel)

    time = db.Column(INT(unsigned=True))
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    avatar = db.Column(db.String(256),
                       default='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg',
                       nullable=False)
    username = db.Column(db.String(32), default='Reminder', nullable=False)

    method = db.Column(db.String(9))

    interval = db.Column(INT(unsigned=True))

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

    def message_content(self):
        if len(self.message.content) > 0:
            return self.message.content
        elif self.message.embed is not None:
            return self.message.embed.description
        else:
            return ''
