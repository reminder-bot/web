from flask import redirect, render_template, request, url_for, session, flash, abort
from app import app, discord, db
from app.models import Guild, Reminder, User, Channel, Role, Message, Embed
from app.markdown import markdown_parse
import os
import io
import requests
import time

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


@app.route('/delete', strict_slashes=False)
def delete():
    reminder = Reminder.query.filter(Reminder.uid == request.args.get('index'))
    reminder.delete(synchronize_session='fetch')

    db.session.commit()

    return '', 200


@app.route('/delete_interval', strict_slashes=False)
def delete_interval():
    r = Reminder.query.filter(Reminder.uid == request.args.get('reminder')).first()

    r.interval = None
    r.enabled = True

    db.session.commit()

    return '', 200


@app.route('/toggle_enabled', strict_slashes=False)
def toggle_enabled():
    reminder = Reminder.query.filter(Reminder.uid == request.args.get('reminder')).first()
    reminder.enabled = not reminder.enabled

    db.session.commit()

    return '', 200


@app.route('/oauth/')
def oauth():
    session.clear()

    return redirect(url_for('discord.login'))


def get_webhook(channel: int):
    # get existing webooks
    webhooks = api_get('channels/{}/webhooks'.format(channel)).json()

    if isinstance(webhooks, list):
        existing = [x for x in webhooks if x['user']['id'] == app.config['DISCORD_OAUTH_CLIENT_ID']]

        if len(existing) == 0:
            # get new webhook
            req = api_post('channels/{}/webhooks'.format(channel), {'name': 'Reminders'}).json()
            wh = 'https://discordapp.com/api/webhooks/{}/{}'.format(req['id'], req['token'])
        else:
            wh = 'https://discordapp.com/api/webhooks/{}/{}'.format(existing[0]['id'], existing[0]['token'])

        return wh

    else:
        return None


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

    current_reminder = None
    current_uid = request.args.get('reminder')

    if current_uid is not None:
        current_reminder = Reminder.query.filter(Reminder.uid == current_uid).first()

        if current_reminder is None:
            flash('Error modifying existing reminder (reminder does not exist)')

            return end()

    user = discord.get('api/users/@me').json()
    try:
        user_id = int(user['id'])

    except KeyError:
        flash('Discord verification failed. Please retry')
        return end()

    member = User.query.filter(User.user == user_id).first()
    guild = Guild.query.filter(Guild.guild == int(request.args.get('redirect'))).first()

    new_msg = request.form.get('message_new')

    try:
        new_channel = int(request.form.get('channel_new'))
        new_time = int(request.form.get('time_new'))

    except:
        flash('Error setting reminder (form data malformed)')

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
            if not avatar or not avatar.startswith('http'):
                avatar = None

        if not (0 < new_time < time.time() + MAX_TIME):
            flash('Error setting reminder (time is too long)')

        elif new_channel == member.dm_channel or new_channel in [x.channel for x in guild.channels]:

            if new_msg is not None and not 0 < len(new_msg) < 2048:
                flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

            elif new_interval is not None and not MIN_INTERVAL < new_interval < MAX_TIME:
                flash('Error setting reminder (interval timer is out of range 800s < t < 50yr)')

            else:
                if request.args.get('id') != '0':
                    webhook = get_webhook(new_channel)

                else:
                    webhook = None

                if current_reminder is None and new_msg is not None:

                    m = Message(content=new_msg)

                    reminder = Reminder(
                        message=m,
                        time=new_time,
                        channel=new_channel,
                        method='dashboard',
                        webhook=webhook,
                        username=username,
                        avatar=avatar,
                        enabled=True,
                        interval=new_interval)

                    db.session.add(reminder)

                # updating an old reminder
                elif new_msg is None:
                    current_reminder.time = new_time
                    current_reminder.channel = new_channel
                    current_reminder.webhook = webhook
                    current_reminder.username = username
                    current_reminder.avatar = avatar
                    current_reminder.interval = new_interval

                # in a DM
                elif guild is None:
                    current_reminder.message.content = new_msg
                    current_reminder.time = new_time
                    current_reminder.interval = new_interval

                else:
                    flash('Message not found for new reminder')

                db.session.commit()

        elif new_channel not in [x.channel for x in guild.channels]:
            flash('Error setting reminder (channel not found)')

        return end()


@app.route('/cache/', methods=['GET'])
def cache():
    def create_cached_user(data: dict) -> User:
        new_caching_user = User(user=data['id'], name='{}#{}'.format(data['username'], data['discriminator']))
        dm_channel = api_post('users/@me/channels', {'recipient_id': data['id']}).json()

        new_caching_user.dm_channel = dm_channel['id']

        db.session.add(new_caching_user)

        return new_caching_user

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

            guild_data = guild_query.first() or Guild(guild=data['id'])

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
        return 'You must Authorize with Discord OAuth to use the web dashboard.'

    else:
        user: dict = discord.get('api/users/@me').json()

        session['user_id'] = user['id']

        user_query = User.query.filter(User.user == user['id'])
        cached_user: User = user_query.first() or create_cached_user(user)

        cached_user.patreon = check_user_patreon(cached_user) > 0

        cached_user.guilds = get_user_guilds()

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

        guild_reminders = Reminder.query.filter(
            Reminder.channel.in_(
                [x.channel for x in accessing_guild.channels])
            ).order_by(Reminder.time).all()

        if request.args.get('refresh') is None:

            return render_template('dashboard.html',
                                   out=False,
                                   guilds=member.guilds,
                                   reminders=guild_reminders,
                                   guild=accessing_guild,
                                   member=member,
                                   time=time.time())

        else:
            return redirect(url_for('dashboard', id=accessing_guild.guild))

    if not discord.authorized:
        # if the user isn't authorized through oauth yet
        return redirect(url_for('oauth'))

    else:
        try:
            user = discord.get('api/users/@me').json()

        except:
            return redirect(url_for('oauth'))

        else:
            user_id: int = user['id']  # get user id from oauth

            member = User.query.filter(User.user == user_id).first()

            if member is None:
                return redirect(url_for('cache'))

            elif request.args.get('id') is not None:
                try:
                    guild_id = int(request.args.get('id'))

                except:  # Guild ID is invalid
                    flash('Guild not found')
                    return redirect(url_for('dashboard'))

                else:
                    if guild_id == 0:
                        channels = [member.dm_channel]
                        reminders = Reminder.query.filter(Reminder.channel == channels[0]).order_by(
                            Reminder.time).all()  # fetch reminders

                        return render_template('dashboard.html',
                                               out=False,
                                               guilds=member.guilds,
                                               reminders=reminders,
                                               guild=None,
                                               member=member,
                                               time=time.time())

                    else:
                        for guild in member.guilds:
                            if guild.guild == guild_id:
                                return permitted_access(guild)

                        else:
                            flash('No permissions to view guild')
                            return redirect(url_for('dashboard'))

            elif request.args.get('refresh') is None:

                return render_template('dashboard.html',
                                       out=True,
                                       guilds=member.guilds,
                                       guild=None,
                                       member=member,
                                       time=time.time())

            else:
                return redirect(url_for('cache'))


@app.route('/dashboard/ame/<int:guild_id>/<reminder_uid>', methods=['GET'])
def advanced_message_editor(guild_id: int, reminder_uid: str):
    try:
        user = discord.get('api/users/@me').json()

    except:
        return redirect(url_for('oauth'))

    else:

        user_id: int = user['id']  # get user id from oauth

        member = User.query.filter(User.user == user_id).first()
        server = GuildData.query.filter(GuildData.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif server not in member.guilds:
            return abort(403)

        else:
            reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first()

            return render_template('advanced_message_editor.html',
                                   guilds=member.guilds,
                                   guild=server,
                                   member=member,
                                   message=reminder.message,
                                   reminder_uid=reminder_uid)


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
            reminder.message.embed = Embed(
                title=field('embed_title'),
                description=field('embed_description'),
                color=color.color)

    else:
        if reminder.message.embed is not None:
            db.session.delete(reminder.message.embed)

        reminder.message.embed = None

    reminder.message.content = field('message_content')

    db.session.commit()

    return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))
