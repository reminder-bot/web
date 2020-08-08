from app import db
import secrets
from sqlalchemy.dialects.mysql import BIGINT, MEDIUMINT, INTEGER as INT, MEDIUMBLOB, TIMESTAMP, ENUM
from datetime import datetime, timedelta

guild_users = db.Table('guild_users',
                       db.Column('guild', INT(unsigned=True), db.ForeignKey('guilds.id'), nullable=False),
                       db.Column('user', INT(unsigned=True), db.ForeignKey('users.id'), nullable=False),
                       db.Column('can_access', db.Boolean, nullable=False, default=False),
                       db.UniqueConstraint('guild', 'user'),
                       )


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(INT(unsigned=True), primary_key=True)
    user = db.Column(BIGINT(unsigned=True), unique=True)

    patreon = db.Column(db.Boolean, nullable=False, default=False)
    dm_channel = db.Column(INT(unsigned=True), db.ForeignKey('channels.id', ondelete='SET NULL'), nullable=False)
    channel = db.relationship('Channel')
    language = db.Column(db.String(2), nullable=False, default='EN')
    name = db.Column(db.String(37))

    def permitted_guilds(self):
        joins = db.session.query(guild_users) \
            .filter(guild_users.c.user == self.id) \
            .filter(guild_users.c.can_access) \
            .all()

        return Guild.query.filter(Guild.id.in_([row.guild for row in joins])).all()

    def set_permitted_guilds(self, guilds):
        stmt = guild_users.update().where(guild_users.c.user == self.id).values(can_access=False)
        db.engine.execute(stmt)

        current_guilds = set(
            x.guild for x in db.session.query(guild_users)
                .filter(guild_users.c.user == self.id)

        )

        for guild in guilds:

            if guild.id in current_guilds:
                stmt = guild_users.update()\
                    .where((guild_users.c.user == self.id) & (guild_users.c.guild == guild.id))\
                    .values(can_access=True)
                db.session.execute(stmt)

            elif guild.id is not None:
                db.session.execute(guild_users.insert().values(guild=guild.id, user=self.id, can_access=True))

        db.session.commit()


class Embed(db.Model):
    __tablename__ = 'embeds'

    id = db.Column(INT(unsigned=True), primary_key=True)

    title = db.Column(db.String(256), nullable=False, default='')
    description = db.Column(db.String(2048), nullable=False, default='')

    image_url = db.Column(db.String(512), nullable=True)
    thumbnail_url = db.Column(db.String(512), nullable=True)

    footer = db.Column(db.String(2048), nullable=False, default='')
    footer_icon = db.Column(db.String(512), nullable=True)

    color = db.Column(MEDIUMINT(unsigned=True), nullable=False, default=0x0)


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(INT(unsigned=True), primary_key=True)

    content = db.Column(db.String(2048), nullable=False, default='')
    tts = db.Column(db.Boolean, nullable=False, default=False)
    embed_id = db.Column(INT(unsigned=True), db.ForeignKey(Embed.id))
    embed = db.relationship(Embed)

    attachment = db.Column(MEDIUMBLOB, nullable=True)
    attachment_name = db.Column(db.String(260), nullable=True)


class Guild(db.Model):
    __tablename__ = 'guilds'

    id = db.Column(INT(unsigned=True), primary_key=True)
    guild = db.Column(BIGINT(unsigned=True), unique=True)
    name = db.Column(db.String(100))

    prefix = db.Column(db.String(5), default="$", nullable=False)
    timezone = db.Column(db.String(30), default="UTC", nullable=False)

    default_channel_id = db.Column(INT(unsigned=True), db.ForeignKey('channels.id', ondelete='SET NULL'))
    default_username = db.Column(db.String(32))
    default_avatar = db.Column(db.String(512))

    default_channel = db.relationship('Channel', foreign_keys=[default_channel_id])

    channels = db.relationship('Channel', backref='guild', lazy='dynamic', foreign_keys='[Channel.guild_id]')
    roles = db.relationship('Role', backref='guild', lazy='dynamic')

    users = db.relationship(
        'User', secondary=guild_users,
        primaryjoin=(guild_users.c.guild == id),
        secondaryjoin='(guild_users.c.user == User.id)',
        backref=db.backref('guilds', lazy='dynamic'), lazy='dynamic'
    )

    command_restrictions = db.relationship('CommandRestriction', backref='guild', lazy='dynamic')
    todo_list = db.relationship('Todo', backref='guild', lazy='dynamic')


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(INT(unsigned=True), primary_key=True)
    role = db.Column(BIGINT(unsigned=True), unique=True, nullable=False)
    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id), nullable=False)

    name = db.Column(db.String(100))

    def display_name(self):
        return self.name or str(self.id)


class CommandRestriction(db.Model):
    __tablename__ = 'command_restrictions'

    id = db.Column(db.Integer, primary_key=True)

    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id, ondelete='CASCADE'), nullable=False)
    role_id = db.Column(INT(unsigned=True), db.ForeignKey(Role.id, ondelete='CASCADE'), nullable=False)
    role = db.relationship(Role)
    command = db.Column(ENUM('todos', 'natural', 'remind', 'interval', 'timer', 'del', 'look', 'alias'))

    db.UniqueConstraint('role', 'command')


class Channel(db.Model):
    __tablename__ = 'channels'

    id = db.Column(INT(unsigned=True), primary_key=True)
    channel = db.Column(BIGINT(unsigned=True), unique=True)
    name = db.Column(db.String(100))

    blacklisted = db.Column(db.Boolean, nullable=False, default=False)

    webhook_id = db.Column(BIGINT(unsigned=True), unique=True)
    webhook_token = db.Column(db.Text)

    paused = db.Column(db.Boolean, nullable=False, default=False)
    paused_until = db.Column(TIMESTAMP)

    guild_id = db.Column(INT(unsigned=True), db.ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return '{}.{}'.format(self.name, self.channel)

    def __hash__(self):
        return self.id.__hash__()

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


class Todo(db.Model):
    __tablename__ = 'todos'

    id = db.Column(INT(unsigned=True), primary_key=True)

    user_id = db.Column(INT(unsigned=True), db.ForeignKey(User.id, ondelete='CASCADE'))
    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id, ondelete='CASCADE'))
    channel_id = db.Column(INT(unsigned=True), db.ForeignKey(Channel.id, ondelete='SET NULL'))
    channel = db.relationship(Channel, backref='todo_list')

    value = db.Column(db.String(2000), nullable=False)


class CommandAlias(db.Model):
    __tablename__ = 'command_aliases'

    id = db.Column(INT(unsigned=True), primary_key=True)

    guild_id = db.Column(
        INT(unsigned=True), db.ForeignKey(Guild.id, ondelete='CASCADE'), nullable=False)
    guild = db.relationship(Guild, backref='aliases')
    name = db.Column(db.String(12), nullable=False)

    command = db.Column(db.String(2048), nullable=False)

    db.UniqueConstraint('guild_id', 'name')


class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column(INT(unsigned=True), primary_key=True, unique=True)
    uid = db.Column(db.String(64), unique=True, default=lambda: Reminder.create_uid())

    name = db.Column(db.String(24), default='Reminder')

    message_id = db.Column(INT(unsigned=True), db.ForeignKey(Message.id), nullable=False)
    message = db.relationship(Message)

    channel_id = db.Column(INT(unsigned=True), db.ForeignKey(Channel.id), nullable=True)
    channel = db.relationship(Channel, backref='reminders')

    time = db.Column(INT(unsigned=True))
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    avatar = db.Column(db.String(512),
                       default='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg',
                       nullable=False)
    username = db.Column(db.String(32), default='Reminder', nullable=False)

    interval = db.Column(INT(unsigned=True))

    method = db.Column(ENUM('remind', 'natural', 'dashboard', 'todo'))
    set_by = db.Column(INT(unsigned=True), db.ForeignKey(User.id, ondelete='SET NULL'), nullable=True)
    set_at = db.Column(TIMESTAMP, nullable=True, default=datetime.now, server_default='CURRENT_TIMESTAMP')

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


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(INT(unsigned=True), primary_key=True)
    time = db.Column(TIMESTAMP, default=datetime.now, server_default='CURRENT_TIMESTAMP()', nullable=False)

    event_name = db.Column(ENUM('edit', 'enable', 'disable', 'delete'), nullable=False)
    bulk_count = db.Column(INT(unsigned=True))

    guild_id = db.Column(INT(unsigned=True), db.ForeignKey(Guild.id, ondelete='CASCADE'), nullable=False)
    guild = db.relationship(Guild)

    user_id = db.Column(INT(unsigned=True), db.ForeignKey(User.id, ondelete='SET NULL'))
    user = db.relationship(User)

    reminder_id = db.Column(INT(unsigned=True), db.ForeignKey(Reminder.id, ondelete='SET NULL'))
    reminder = db.relationship(Reminder)

    @classmethod
    def new_edit_event(cls, reminder, user_id):

        if reminder.channel.guild_id is not None:
            q = cls.query \
                .filter(cls.guild_id == reminder.channel.guild_id) \
                .filter(cls.time > (datetime.now() - timedelta(hours=2))) \
                .first()

            if q is None or q.user_id != user_id:
                event = cls(event_name='edit', guild_id=reminder.channel.guild_id, user_id=user_id, reminder=reminder)
                db.session.add(event)
