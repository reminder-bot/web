from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder, Interval, User, PartialMember, GuildData, ChannelData, RoleData
from app.markdown import markdown_parse
import os
import io
import requests
import json
import time

MAX_TIME = 1576800000
MIN_INTERVAL = 800

class Color():
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
            if 0 < color_hex < 16**6:
                return Color(failed=True)

            else:
                return Color(color=color_hex)


@app.errorhandler(500)
def internal_error(error):
    session.clear()
    return "An error has occured! We've made a report, and cleared your cache on this website. If you encounter this error again, please send us a message on Discord!"


@app.route('/')
def index():
    return redirect( url_for('help') )


@app.route('/help/')
def help():
    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html', help=s['help_raw'], languages=all_langs, title='Help', logo='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg')


@app.route('/updates/<log>')
def updates(log):
    
    try:
        with open('app/updates/{}'.format(log), 'r') as f:
            fr = f.readlines()

        return render_template('update.html', content=markdown_parse(fr), title='Update', logo='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg')

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
    interval = Interval.query.filter((Interval.reminder == r.id) & (Interval.id == request.args.get('interval')))

    if interval.first() is not None:
        all_switching = Interval.query.filter((Interval.reminder == r.id) & (Interval.position > interval.first().position))

        for i in all_switching:
            i.position -= 1

    interval.delete(synchronize_session='fetch')

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
    return requests.get('https://discordapp.com/api/{}'.format(endpoint), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})

def api_post(endpoint, data):
    return requests.post('https://discordapp.com/api/{}'.format(endpoint), json=data, headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


@app.route('/creminder', methods=['POST'])
def change_reminder():
    user = discord.get('api/users/@me').json()
    user_id = int(user['id'])

    member = User.query.filter(User.user == user_id).first()
    guild = GuildData.query.filter(GuildData.guild == int(request.args.get('redirect'))).first()

    try:
        new_msg = request.form.get('message_new')
        new_channel = int(request.form.get('channel_new'))
        new_time = int(request.form.get('time_new'))

    except:
        flash('Error setting reminder (form data malformed)')
        
        if request.args.get('redirect'):
            return redirect(url_for('dashboard', id=request.args.get('redirect')))
        
        else:
            return redirect( url_for('dashboard') )

    else:
        new_interval = None
        multiplier = None
        embed = None
        avatar = None
        username = None

        enabled = 'on' in request.form.getlist('enabled') or request.form.get('enabled') is None

        username = request.form.get('username')
        if username is not None:
            if not (0 < len(username) <= 32):
                username = None

        if member.patreon > 0:
            try:
                new_interval = int(request.form.get('interval_new'))
                multiplier = int(request.form.get('multiplier_new'))
            except ValueError:
                new_interval = None

            if request.form.get('embed') == 'on':
                embed_color = Color.decode(request.form.get('color')[1:])
                embed = embed_color.color

                if embed_color.failed:
                    print('Failed to decode color of "{}". Discarding'.format(request.form.get('color')))

            avatar = request.form.get('avatar')
            if not avatar or not avatar.startswith('http') or not '.' in avatar:
                avatar = None

        if not (0 < int(new_time) < time.time() + MAX_TIME):
            flash('Error setting reminder (time is too long)')

        elif new_msg and (new_channel == member.dm_channel or new_channel in [x.channel for x in guild.channels]):

            if not 0 < len(new_msg) < 2000:
                flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

            elif new_interval is not None and not MIN_INTERVAL < new_interval * multiplier < MAX_TIME:
                flash('Error setting reminder (interval timer is out of bounds)')

            else:
                wh = None

                index = request.args.get('index')

                if index is not None:
                    rem = Reminder.query.filter(Reminder.uid == index).first()

                    if rem is None:
                        flash('Error changing reminder: Reminder not found')

                    else:
                        rem.enabled = enabled
                        rem.message = new_msg
                        rem.time = int( new_time )
                        if int( new_channel ) != rem.channel:
                            rem.channel = int( new_channel )
                            rem.webhook = get_webhook(new_channel)
                        rem.embed = embed
                        rem.method = 'dashboard'

                        if username is not None:
                            rem.username = username

                        if avatar is not None:
                            rem.avatar = avatar

                        if new_interval is not None:
                            prev = rem.intervals.order_by(Interval.position.desc()).first()

                            new_pos = 0 if prev is None else prev.position + 1

                            interval = Interval(reminder=rem.id, period=new_interval * multiplier, position=new_pos)
                            db.session.add(interval)

                        for interval in rem.intervals:
                            field = request.form.get('interval_{}'.format(interval.position))
                            mul_field = request.form.get('multiplier_{}'.format(interval.position))
                            if field is not None and all(x in '0123456789.' for x in field) and mul_field is not None and all(x in '0123456789' for x in mul_field):
                                val = float(field)

                                if MIN_INTERVAL < val < MAX_TIME:
                                    interval.period = val * int(mul_field)

                else:
                    if request.args.get('id') != '0':
                        webhook = get_webhook(new_channel)

                    else:
                        webhook = None

                    reminder = Reminder(
                        message=new_msg,
                        time=int(new_time),
                        channel=int(new_channel),
                        position=0 if new_interval is not None else None,
                        embed=embed,
                        method='dashboard',
                        webhook=webhook,
                        username=username,
                        avatar=avatar,
                        enabled=enabled)

                    db.session.add(reminder)

                    if new_interval is not None:
                        db.session.commit()

                        interval = Interval(reminder=reminder.id, period=new_interval * multiplier, position=0)
                        db.session.add(interval)

                db.session.commit()

        elif new_channel not in [x.channel for x in guild.channels]:
            flash('Error setting reminder (channel not found)')

        if request.args.get('redirect'):
            return redirect(url_for('dashboard', id=request.args.get('redirect')))
        
        else:
            return redirect(url_for('dashboard'))


@app.route('/cache/', methods=['GET'])
def cache():

    def create_cached_user(data: dict) -> User:
        user = User(user=data['id'], name=data['username'])
        dmchannel = api_post('users/@me/channels', {'recipient_id': data['id']}).json()

        user.dm_channel = dmchannel['id']

        db.session.add(user)

        return user

    def check_user_patreon(user: User) -> int:
        reminder_guild_member = api_get('guilds/{}/members/{}'.format(app.config['PATREON_SERVER'], user.user))
        if reminder_guild_member.status_code == 200:
            roles = list(set([int(x) for x in reminder_guild_member.json()['roles']]) & set(app.config['PATREON_ROLES']))
            return len(roles)

        else:
            return 0

    def get_user_guilds(user: User) -> list:

        def form_cached_guild(data: dict) -> GuildData:
            guild_query = GuildData.query.filter(GuildData.guild == data['id'])

            guild = guild_query.first() or GuildData(guild=data['id'])

            guild.name = data['name']

            return guild

        guilds: list = discord.get('api/users/@me/guilds').json()
        cached_guilds: list = []

        for guild in guilds:
            if guild['permissions'] & 0x00002028 or guild['owner']:
                cached_guild: GuildData = form_cached_guild(guild)

                cached_guilds.append(cached_guild)

        return cached_guilds

    user: dict = discord.get('api/users/@me').json()

    session['user_id'] = user['id']

    user_query = User.query.filter(User.user == user['id'])
    cached_user: User = user_query.first() or create_cached_user(user)

    cached_user.patreon = check_user_patreon(cached_user)

    db.session.commit()

    cached_user.guilds = get_user_guilds(cached_user)

    return redirect( url_for('dashboard') )


@app.route('/dashboard/', methods=['GET'])
def dashboard():

    def permitted_access(guild: GuildData):
        if request.args.get('refresh') is not None:
            print('Refreshing guild data for {}'.format(guild_id))

            server_data = Server.query.filter( Server.server == guild.guild ).first()

            if server_data is None:
                flash('Guild not found')
                return redirect( url_for('dashboard') )

            else:
                try:
                    channels = [x for x in api_get('guilds/{}/channels'.format(guild.guild)).json() if isinstance(x, dict) and x['type'] == 0]

                except:
                    flash('Bot no longer in specified guild')
                    return redirect( url_for('dashboard') )

                else:
                    ChannelData.query.filter((ChannelData.guild == guild.guild) & ChannelData.channel.notin_([x['id'] for x in channels])).delete(synchronize_session='fetch')

                    for channel in channels:
                        c = ChannelData.query.filter(ChannelData.channel == channel['id'])

                        if c.count() > 0:
                            ch = c.first()
                            ch.name = channel['name']

                        else:
                            ch = ChannelData(channel=channel['id'], name=channel['name'], guild=guild.guild)
                            db.session.add(ch)

                    members = api_get('guilds/{}/members?limit=150'.format(guild.guild)).json()

                    guild.partials = []

                    for me in members:
                        m = PartialMember.query.filter(PartialMember.user == me['user']['id']).first()

                        if m is not None:
                            m.name = me['user']['username']

                        else:
                            m = PartialMember(user=me['user']['id'], name=me['user']['username'])
                            db.session.add(m)

                        guild.partials.append(m)


                    roles = api_get('guilds/{}/roles'.format(guild.guild)).json()

                    RoleData.query.filter((RoleData.guild == guild_id) & RoleData.role.notin_([x['id'] for x in roles])).delete(synchronize_session='fetch')

                    for role in roles:
                        c = RoleData.query.filter(RoleData.role == role['id'])

                        if c.count() > 0:
                            ch = c.first()
                            ch.name = role['name']

                        else:
                            ch = RoleData(role=role['id'], name=role['name'], guild=guild_id)
                            db.session.add(ch)

                    db.session.commit()

        guild = GuildData.query.filter(GuildData.guild == guild_id).first()
        server = Server.query.filter(Server.server == guild_id).first()
        reminders = Reminder.query.filter(Reminder.channel.in_([x.channel for x in guild.channels])).order_by(Reminder.time).all() # fetch reminders

        if guild is not None:
            for reminder in reminders: # assign channel names to all reminders
                for channel in guild.channels:
                    if reminder.channel == channel.channel:
                        reminder.channel_name = channel.name
                        break

        if request.args.get('refresh') is None:

            return render_template('dashboard.html',
                out=False,
                guilds=member.guilds,
                reminders=reminders,
                guild=guild,
                server=server,
                member=member,
                time=time.time())

        else:
            return redirect( url_for('dashboard', id=guild.guild) )

    if not discord.authorized:
        # if the user isn't authorized through oauth yet
        return redirect( url_for('oauth') )

    else:
        try:
            user = discord.get('api/users/@me').json()

        except:
            return redirect( url_for('oauth') )

        else:
            user_id: int = user['id'] # get user id from oauth

            member = User.query.filter(User.user == user_id).first()

            if member is None:
                return redirect( url_for('cache') )

            elif request.args.get('id') is not None:
                try:
                    guild_id = int(request.args.get('id'))

                except: # Guild ID is invalid
                    flash('Guild not found')
                    return redirect( url_for('dashboard') )

                if guild_id == 0:
                    channels = [member.dm_channel]
                    reminders = Reminder.query.filter(Reminder.channel == channels[0]).order_by(Reminder.time).all() # fetch reminders

                    return render_template('dashboard.html',
                        out=False,
                        guilds=member.guilds,
                        reminders=reminders,
                        guild=None,
                        server=None,
                        member=member,
                        time=time.time())

                else:
                    for guild in member.guilds:
                        if guild.guild == guild_id:
                            return permitted_access(guild)

                    else:
                        flash('No permissions to view guild')
                        return redirect( url_for('dashboard') )

            elif request.args.get('refresh') is None:
                
                return render_template('dashboard.html',
                    out=True,
                    guilds=member.guilds,
                    guild=None,
                    server=None,
                    member=member,
                    time=time.time())

            else:
                return redirect( url_for('dashboard') )