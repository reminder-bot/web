import typing
from flask import redirect, render_template, request, url_for, session, flash, abort, jsonify, send_file
from app import app, discord, db
from app.models import Guild, Reminder, User, Channel, Role, Message, Embed, Event, CommandRestriction
from app.markdown import markdown_parse
import os
import io
import requests
import time
import itertools

MAX_TIME = 1576800000
MIN_INTERVAL = 800
LOGO_URL = 'https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg'


class Color:
    def __init__(self, color: int = None, failed: bool = False):
        self.color: int = color
        self.failed: bool = failed

    @staticmethod
    def decode(color: str) -> 'Color':
        try:
            color_hex = int(color, 16)

        except:
            return Color(failed=True)

        else:
            if 0 <= color_hex <= 0xFFFFFF:
                return Color(color=color_hex)

            else:
                return Color(failed=True)


def get_internal_id():
    if (internal_id := session.get('internal_id')) is not None:
        return internal_id

    else:
        user_id = session.get('user_id')

        if user_id is None:
            user = discord.get('api/users/@me').json()

            user_id = int(user['id'])
            session['user_id'] = user_id

        user_record = User.query.filter(User.user == user_id).first()

        if user_record is not None:
            session['internal_id'] = user_record.id

            return user_record.id

        else:
            raise Exception('No user record')


@app.errorhandler(500)
def internal_error(_error):
    session.clear()
    return "An error has occurred! We've made a report, and cleared your session cache on this website. If you " \
           "encounter this error again, please send us a message on Discord!"


@app.route('/')
def index():
    return redirect(url_for('help_page'))


@app.route('/help/')
def help_page():
    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help_page'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html', help=s['help_raw'], languages=all_langs, title='Help', language=lang,
                           logo=LOGO_URL)


@app.route('/updates/<log>')
def updates(log):
    try:
        with open('app/updates/{}'.format(log), 'r') as f:
            fr = f.readlines()

        return render_template('update.html', content=markdown_parse(fr), title='Update',
                               logo=LOGO_URL)

    except FileNotFoundError:
        return redirect('https://jellywx.com')


@app.route('/delete_reminder/', methods=['POST'])
def delete_reminder():
    reminder_q = Reminder.query.filter(Reminder.uid == request.json['uid'])
    reminder = reminder_q.first()

    if reminder.channel.guild_id is not None:
        event = Event(event_name='delete', guild_id=reminder.channel.guild_id, user_id=get_internal_id())
        db.session.add(event)

    reminder_q.delete(synchronize_session='fetch')

    db.session.commit()

    return '', 200


@app.route('/delete_interval/', methods=['POST'])
def delete_interval():
    reminder = Reminder.query.filter(Reminder.uid == request.json['uid']).first()

    reminder.interval = None
    reminder.enabled = True

    Event.new_edit_event(reminder, get_internal_id())

    db.session.commit()

    return '', 200


@app.route('/toggle_enabled/', methods=['POST'])
def toggle_enabled():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        reminder.enabled = not reminder.enabled

        if reminder.channel.guild_id is not None:
            name = 'enable' if reminder.enabled else 'disable'

            event = Event(
                event_name=name, guild_id=reminder.channel.guild_id, user_id=get_internal_id(), reminder=reminder)
            db.session.add(event)

        db.session.commit()

        return jsonify({'enabled': reminder.enabled})

    else:
        return 'Reminder not found', 404


@app.route('/change_name/', methods=['POST'])
def change_name():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        name = request.json['name']

        if len(name) <= 24:
            reminder.name = name

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        else:
            return 'Name too long. Please use a maximum of 24 characters', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_username/', methods=['POST'])
def change_username():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        username = request.json['username']

        if len(username) <= 32:
            reminder.username = username

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        else:
            return 'Username too long. Please use a maximum of 32 characters', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_message/', methods=['POST'])
def change_message():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        message = request.json['message']

        if 0 < len(message) <= 2048:
            reminder.message.content = message

            db.session.commit()

            return '', 200

        elif 0 < len(message):
            return 'Message too short. Please use at least 1 character', 400

        else:
            return 'Message too long. Please use a maximum of 2048 characters', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_avatar/', methods=['POST'])
def change_avatar():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        avatar = request.json['avatar']

        if len(avatar) <= 512:
            reminder.avatar = avatar

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        else:
            return 'Avatar URL too long. Please use a maximum of 512 characters', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_channel/', methods=['POST'])
def change_channel():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:

        if (channel := Channel.query.filter(Channel.channel == int(request.json['channel'])).first()) is not None:
            reminder.channel = channel

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        else:
            return 'Channel not found', 404

    else:
        return 'Reminder not found', 404


@app.route('/change_time/', methods=['POST'])
def change_time():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:
        new_time = request.json['time']

        if new_time is not None and 0 < new_time < time.time() + MAX_TIME:
            reminder.time = new_time

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        elif new_time < 0:
            return 'Time cannot be less than zero', 400

        elif new_time > time.time() + MAX_TIME:
            return 'Time must be less than {} seconds in the future'.format(MAX_TIME), 400

        elif new_time is None:
            return 'Something went wrong with client-side time processing. Please refresh the page', 400

        else:
            return 'This error should never happen, but something went wrong', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_interval/', methods=['POST'])
def change_interval():
    member = User.query.get(get_internal_id())

    if member.patreon:
        reminder = Reminder.query.filter(Reminder.uid == request.json['uid']).first()
        interval = request.json['interval']

        if reminder is not None:
            if interval is not None and MIN_INTERVAL <= interval < MAX_TIME:
                reminder.interval = interval

                Event.new_edit_event(reminder, get_internal_id())

                db.session.commit()

                return '', 200

            elif interval is None:
                reminder.interval = None

                Event.new_edit_event(reminder, get_internal_id())

                db.session.commit()

                return '', 200

            elif MIN_INTERVAL > interval:
                return 'Interval too short (must be longer than {} seconds'.format(MIN_INTERVAL), 400

            elif interval > MAX_TIME:
                return 'Interval too long (must be shorter than {} seconds'.format(MAX_TIME), 400

            else:
                return 'This error should never appear, but something went wrong', 400

        else:
            return 'Reminder not found', 404

    else:
        return 'Patreon required', 403


@app.route('/change_restrictions/', methods=['PATCH'])
def change_restrictions():
    if (guild_id := request.json.get('guild_id')) and \
            (command := request.json.get('command')) and \
            (roles := request.json.get('roles')) is not None:

        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:
            guild = Guild.query.get(guild_id)

            guild.command_restrictions.filter(CommandRestriction.command == command).delete(synchronize_session='fetch')

            valid_ids = [r.id for r in guild.roles]

            for role in filter(lambda r: int(r) in valid_ids, roles):
                c = CommandRestriction(role_id=role, guild_id=guild_id, command=command)
                db.session.add(c)

            db.session.commit()

            return '', 201
    else:
        abort(400)


@app.route('/oauth/')
def oauth():
    session.clear()

    return redirect(url_for('discord.login'))


def api_get(endpoint):
    return requests.get('https://discordapp.com/api/{}'.format(endpoint),
                        headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


def api_post(endpoint, data):
    return requests.post('https://discordapp.com/api/{}'.format(endpoint), json=data,
                         headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


@app.route('/creminder', methods=['POST'])
def change_reminder():
    def end():
        if request.args.get('redirect'):
            return redirect(url_for('dashboard', id=request.args.get('redirect')))

        else:
            return redirect(url_for('dashboard'))

    user = discord.get('api/users/@me').json()
    try:
        user_id = int(user['id'])

    except KeyError:
        flash('Discord verification failed. Please retry')
        return end()

    member = User.query.filter(User.user == user_id).first()
    guild = Guild.query.filter(Guild.guild == int(request.args.get('redirect'))).first()

    new_msg = request.form.get('message_new')

    if new_msg is None or len(new_msg) == 0:
        flash('Error setting reminder (no message provided')

        return end()
    else:
        try:
            new_channel = int(request.form.get('channel_new'))
            new_time = int(request.form.get('time_new'))

        except:
            flash('Error setting reminder (time or channel missing)')

            return end()

        else:
            new_interval = None
            avatar = LOGO_URL

            username = request.form.get('username') or 'Reminder'
            if not (0 < len(username) <= 32):
                username = 'Reminder'

            if member.patreon:
                try:
                    new_interval = int(request.form.get('interval_new')) * int(request.form.get('multiplier_new'))

                except:
                    new_interval = None

                avatar = request.form.get('avatar')
                if not isinstance(avatar, str) or not avatar.startswith('http'):
                    avatar = None

            if not (0 < new_time < time.time() + MAX_TIME):
                flash('Error setting reminder (time is too long)')

            elif new_channel == -1 or new_channel in [x.channel for x in guild.channels]:

                if new_msg is not None and not 0 < len(new_msg) < 2048:
                    flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

                elif new_interval is not None and not MIN_INTERVAL < new_interval < MAX_TIME:
                    flash('Error setting reminder (interval timer is out of range 800s < t < 50yr)')

                else:
                    if new_channel != -1:
                        channel = Channel.query.filter(Channel.channel == new_channel).first_or_404()

                        if (channel.webhook_id or channel.webhook_token) is None:
                            channel.update_webhook(api_get, api_post, app.config['DISCORD_OAUTH_CLIENT_ID'])

                        channel_id = channel.id
                    else:
                        channel_id = member.dm_channel

                    m = Message(content=new_msg)

                    reminder = Reminder(
                        message=m,
                        time=new_time,
                        channel_id=channel_id,
                        method='dashboard',
                        username=username,
                        avatar=avatar,
                        enabled=True,
                        interval=new_interval,
                        set_by=member.id)

                    db.session.add(reminder)

                    db.session.commit()

            elif new_channel not in [x.channel for x in guild.channels]:
                flash('Error setting reminder (channel not found)')

            return end()


@app.route('/cache/', methods=['GET'])
def cache():
    def check_user_patreon(checking_user: User) -> int:
        reminder_guild_member = api_get('guilds/{}/members/{}'.format(app.config['PATREON_SERVER'], checking_user.user))

        if reminder_guild_member.status_code == 200:
            roles = [int(x) for x in reminder_guild_member.json()['roles']]
            return app.config['PATREON_ROLE'] in roles

        else:
            return 0

    def get_user_guilds() -> list:

        def form_cached_guild(data: dict) -> Guild:
            guild_query = Guild.query.filter(Guild.guild == data['id'])

            if (guild_data := guild_query.first()) is not None:
                guild_data.name = data['name']

                return guild_data

            else:
                guild_data = Guild(guild=data['id'])
                db.session.add(guild_data)
                db.session.flush()

                guild_data.name = data['name']

                return guild_data

        guilds: list = discord.get('api/users/@me/guilds').json()
        cached_guilds: list = []

        for guild in guilds:

            if guild['permissions'] & 0x00002028 or guild['owner']:
                cached_guild: Guild = form_cached_guild(guild)

                cached_guilds.append(cached_guild)

        return cached_guilds

    if not discord.authorized:
        return render_template('dashboard_error.html', error_message='You must Authorize with Discord OAuth to '
                                                                     'use the web dashboard.')
    else:
        user: dict = discord.get('api/users/@me').json()

        session['user_id'] = int(user['id'])

        user_query = User.query.filter(User.user == int(user['id']))
        cached_user: typing.Optional[User] = user_query.first()

        if cached_user is None:
            return render_template('dashboard_error.html',
                                   error_message='You need to interact with the bot at least '
                                                 'once within Discord before using the dashboard')

        else:
            session['internal_id'] = cached_user.id

            cached_user.name = user['username']

            cached_user.patreon = check_user_patreon(cached_user) > 0

            cached_user.set_permitted_guilds(get_user_guilds())

            db.session.commit()

            return redirect(url_for('dashboard'))


@app.route('/dashboard/', methods=['GET'])
def dashboard():
    def permitted_access(accessing_guild: Guild):
        # if user wants to refresh the guild's data (syncing members and shit)
        if request.args.get('refresh') is not None:
            print('Refreshing guild data for {}'.format(accessing_guild.guild))

            try:
                guild_channels = [x for x in api_get('guilds/{}/channels'.format(accessing_guild.guild)).json() if
                                  isinstance(x, dict) and x['type'] == 0]

            except:
                flash('Bot no longer in specified guild')
                return redirect(url_for('dashboard'))

            else:
                Channel.query.filter((Channel.guild == accessing_guild) & Channel.channel.notin_(
                    [x['id'] for x in guild_channels])).delete(synchronize_session='fetch')

                for channel in guild_channels:
                    c = Channel.query.filter(Channel.channel == channel['id'])

                    if c.count() > 0:
                        ch = c.first()
                        ch.name = channel['name']
                        ch.guild_id = accessing_guild.id

                    else:
                        ch = Channel(channel=channel['id'], name=channel['name'], guild=accessing_guild)
                        db.session.add(ch)

                roles = api_get('guilds/{}/roles'.format(accessing_guild.guild)).json()

                Role.query.filter(
                    (Role.guild_id == guild_id) & Role.role.notin_([x['id'] for x in roles])).delete(
                    synchronize_session='fetch')

                for role in roles:
                    r = Role.query.filter(Role.role == role['id'])

                    if r.count() > 0:
                        ro = r.first()
                        ro.name = role['name']

                    else:
                        ro = Role(role=role['id'], name=role['name'], guild=accessing_guild)
                        db.session.add(ro)

                db.session.commit()

        channel_ids = [channel.id for channel in guild.channels]
        guild_reminders = Reminder.query.filter(Reminder.channel_id.in_(channel_ids)).order_by(Reminder.time).all()

        if request.args.get('refresh') is None:

            return render_template('reminder_dashboard/reminder_dashboard.html',
                                   guilds=member.permitted_guilds(),
                                   reminders=guild_reminders,
                                   guild=accessing_guild,
                                   member=member)

        else:
            return redirect(url_for('dashboard', id=accessing_guild.guild))

    if not discord.authorized:
        # if the user isn't authorized through oauth yet
        return redirect(url_for('oauth'))

    else:
        member = User.query.get(get_internal_id())

        if member is None:
            return redirect(url_for('cache'))

        elif request.args.get('id') is not None:
            try:
                guild_id = int(request.args.get('id'))

            except:  # Guild ID is invalid
                flash('Guild ID invalid')
                return redirect(url_for('dashboard'))

            else:
                if guild_id == 0:
                    reminders = Reminder.query.filter(Reminder.channel_id == member.dm_channel).order_by(
                        Reminder.time).all()  # fetch reminders

                    return render_template('reminder_dashboard/reminder_dashboard.html',
                                           guilds=member.permitted_guilds(),
                                           reminders=reminders,
                                           guild=None,
                                           member=member)

                else:
                    for guild in member.permitted_guilds():
                        if guild.guild == guild_id:
                            return permitted_access(guild)

                    else:
                        flash('No permissions to view guild')
                        return redirect(url_for('dashboard'))

        elif request.args.get('refresh') is None:

            return render_template('empty_dashboard.html',
                                   guilds=member.permitted_guilds(),
                                   guild=None,
                                   member=member)

        else:
            return redirect(url_for('cache'))


@app.route('/dashboard/ame/<int:guild_id>/<reminder_uid>', methods=['GET'])
def advanced_message_editor(guild_id: int, reminder_uid: str):
    member = User.query.get(get_internal_id())
    guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

    if member is None:
        return redirect(url_for('cache'))

    elif guild not in member.permitted_guilds():
        return abort(403)

    else:
        reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first()

        return render_template('reminder_dashboard/advanced_message_editor.html',
                               guilds=member.permitted_guilds(),
                               guild=guild,
                               member=member,
                               message=reminder.message,
                               reminder_uid=reminder_uid)


@app.route('/dashboard/audit_log')
def audit_log():
    class PseudoEvent:
        def __init__(self, reminder):
            self.event_name = 'create'
            self.bulk_count = None
            self.user = User.query.get(reminder.set_by)
            self.time = reminder.set_at
            self.reminder = reminder

    def combine(a, b):
        out = []

        while len(a) * len(b) > 0:
            if a[0].time > b[0].time:
                out.append(a.pop(0))
            else:
                out.append(b.pop(0))

        if len(a) > 0:
            out.extend(a)

        else:
            out.extend(b)

        return out

    if (guild_id := request.args.get('id')) is not None:
        member = User.query.get(get_internal_id())
        guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif guild not in member.permitted_guilds():
            return abort(403)

        else:
            events = Event.query.filter(Event.guild_id == guild.id).order_by(Event.time.desc())
            pseudo_events = [PseudoEvent(r) for r in itertools.chain(*[c.reminders for c in guild.channels])]

            all_events = combine(events.all(), pseudo_events)

            return render_template('audit_log/audit_log.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   events=all_events)

    else:
        return redirect(url_for('dashboard'))


@app.route('/dashboard/settings')
def settings_dashboard():
    if (guild_id := request.args.get('id')) is not None:
        member = User.query.get(get_internal_id())
        guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif guild not in member.permitted_guilds():
            return abort(403)

        else:

            return render_template('settings_dashboard/settings_dashboard.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   command_restrictions=guild.command_restrictions)

    else:
        return redirect(url_for('dashboard'))


@app.route('/dashboard/update_message/<int:guild_id>/<reminder_uid>', methods=['POST'])
def update_message(guild_id: int, reminder_uid: str):
    reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first_or_404()

    field = request.form.get

    if field('embedded') is not None:
        color = Color.decode(field('embed_color')[1:])

        if color.failed:
            flash('Invalid color')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

        else:
            footer_icon = icon if (icon := field('embed_footer_icon')).startswith('https://') else None

            reminder.message.embed = Embed(
                title=field('embed_title'),
                description=field('embed_description'),
                footer=field('embed_footer'),
                footer_icon=footer_icon,
                color=color.color)

    else:
        if reminder.message.embed is not None:
            db.session.delete(reminder.message.embed)

        reminder.message.embed = None

    if field('attachment_provided') is not None:
        file = request.files['file']

        if file.content_length < 8 * 1024 * 1024 and len(file.filename) <= 32:
            reminder.message.attachment = file.read()
            reminder.message.attachment_name = file.filename

        else:
            flash('File is too large or file name is too long. '
                  'Please upload a maximum of 8MB, with 32 character filename')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

    else:
        reminder.message.attachment = None
        reminder.message.attachment_name = None

    reminder.message.tts = field('tts') is not None

    reminder.message.content = field('message_content')

    Event.new_edit_event(reminder, get_internal_id())

    db.session.commit()

    return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))


@app.route('/download_attachment/<reminder_uid>')
def download_attachment(reminder_uid):
    reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first_or_404()

    if reminder is None or reminder.message.attachment is None:
        abort(404)
    else:
        return send_file(io.BytesIO(reminder.message.attachment), attachment_filename=reminder.message.attachment_name)
