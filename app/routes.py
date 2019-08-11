from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder, Interval, User, PartialMember, GuildData, ChannelData, RoleData
import os
import io
import requests
import json
import time
import secrets


def markdown_parse(contents):
    outlines = []
    for line in contents:
        if len(line.strip()) == 0:
            outlines.append('<br>')

        count = 0
        for char in line:
            if char == '#':
                count += 1
            else:
                break

        line = line.strip('#')

        if count > 0:
            line = '<h{0}>{1}</h{0}>'.format(count, line)

        for x in range(line.count('**')):
            if x % 2 == 0:
                line = line.replace('**', '<strong>', 1)
            else:
                line = line.replace('**', '</strong>', 1)

        for x in range(line.count('__')):
            if x % 2 == 0:
                line = line.replace('__', '<strong>', 1)
            else:
                line = line.replace('__', '</strong>', 1)

        for x in range(line.count('*')):
            if x % 2 == 0:
                line = line.replace('*', '<em>', 1)
            else:
                line = line.replace('*', '</em>', 1)

        for x in range(line.count('_')):
            if x % 2 == 0:
                line = line.replace('_', '<em>', 1)
            else:
                line = line.replace('_', '</em>', 1)

        for x in range(line.count('`')):
            if x % 2 == 0:
                line = line.replace('`', '<code>', 1)
            else:
                line = line.replace('`', '</code>', 1)

        outlines.append(line)

    return '\n'.join(outlines)


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
    webhooks = api_get('channels/{}/webhooks'.format(channel)).json()
    if isinstance(webhooks, list):
        existing = [x for x in webhooks if x['user']['id'] == app.config['DISCORD_OAUTH_CLIENT_ID']]

        if len(existing) == 0:
            wh = requests.post('https://discordapp.com/api/v6/channels/{}/webhooks'.format(channel), json={'name': 'Reminders'}, headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()
            wh = 'https://discordapp.com/api/webhooks/{}/{}'.format(wh['id'], wh['token'])
        else:
            wh = 'https://discordapp.com/api/webhooks/{}/{}'.format(existing[0]['id'], existing[0]['token'])

        return wh

    else:
        return None


def create_uid(i1, i2): # misnomer- not actually a hash in any way, was originally going to be a hash but changed my mind
    m = i2
    while m > 0:
        i1 *= 10
        m //= 10
    
    bigint = i1 + i2
    full = hex(bigint)[2:]
    while len(full) < 64:
        full += secrets.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')

    return full


def api_get(endpoint):
    return requests.get('https://discordapp.com/api/v6/{}'.format(endpoint), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


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
            return redirect(url_for('dashboard'))

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
            try:
                embed = int(request.form.get('color')[1:], 16)
            except:
                embed = None
            else:
                if 0 > embed or embed > 16777215:
                    embed = None

        if member.patreon > 1:
            avatar = request.form.get('avatar')
            if not avatar or not avatar.startswith('http') or not '.' in avatar:
                avatar = None

    if not (0 < int(new_time) < time.time() + 1576800000):
        flash('Error setting reminder (time is too long)')

    elif new_msg and (new_channel == member.dm_channel or new_channel in [x.channel for x in guild.channels]):

        if not 0 < len(new_msg) < 2000:
            flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

        elif new_interval is not None and not 800 < new_interval * multiplier < 1576800000:
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

                            if 800 < val < 1576800000:
                                interval.period = val * int(mul_field)

            else:
                if request.args.get('id') != '0':
                    webhook = get_webhook(new_channel)

                else:
                    webhook = None

                full = create_uid(int(new_channel), int(new_channel))

                reminder = Reminder(
                    message=new_msg,
                    uid=full,
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


@app.route('/dashboard/', methods=['GET', 'POST'])
def dashboard():
    if not discord.authorized:
        return redirect( url_for('oauth') )

    else:
        try:
            user = discord.get('api/users/@me').json()
        except:
            return redirect( url_for('oauth') )

        user_id = user['id'] # get user id from oauth

        m_query = User.query.filter(User.user == user_id)

        if m_query.filter(User.cache_time < time.time()).count() > 0 and request.args.get('refresh') is None: # member located in cache, is in date and no refresh requested
            member = m_query.first()

        else: # need to recache
            member = m_query.first()

            if member is None:
                member = User(user=user_id)
                db.session.add(member)

            member.name = user['username']

            reminder_guild_member = api_get('guilds/{}/members/{}'.format(app.config['PATREON_SERVER'], user_id))
            if reminder_guild_member.status_code == 200:

                roles = list(set([int(x) for x in reminder_guild_member.json()['roles']]) & set(app.config['PATREON_ROLES']))
                member.patreon = len(roles)
                member.cache_time = time.time() + 345600 # 4 day cache period if the user is patreon

            else:
                member.patreon = 0
                member.cache_time = time.time() + 7200 # 2 hour cache period is the user is not patreon ( means it'll get updated if they become patreon )

            channel = requests.post('https://discordapp.com/api/v6/users/@me/channels', json={'recipient_id': user['id']}, headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()
            member.dm_channel = channel['id']

            member.guilds = [] # clear out the guilds via the orm to prep to readd them

            guilds = discord.get('api/users/@me/guilds').json()

            for guild in guilds:

                idx = guild['id']

                s = Server.query.filter_by(server=idx).first()

                if s is None:
                    continue

                elif (guild['permissions'] & 0x00002000) or (guild['permissions'] & 0x00000020) or (guild['permissions'] & 0x00000008):
                    g_query = GuildData.query.filter(GuildData.guild == idx)

                    if g_query.filter(GuildData.cache_time < time.time()).count() > 0:
                        member.guilds.append(g_query.first())

                    else:
                        g = g_query.first()

                        if g is None:
                            g = GuildData(guild=idx, name=guild['name'], cache_time=0) # empty cache so set cache time to something low
                            db.session.add(g)
                            
                        member.guilds.append(g)

            db.session.commit()
        # end of usercache procedure

        if request.args.get('id') is not None:
            try:
                guild_id = int(request.args.get('id'))
            except:
                flash('Guild not found')
                return redirect( url_for('dashboard') )

            if guild_id == 0:
                channels = [member.dm_channel]

            else:
                for guild in member.guilds:
                    if guild.guild == guild_id:
                        server_data = Server.query.filter( Server.server == guild_id ).first()

                        if server_data is None:
                            flash('Guild not found')
                            return redirect( url_for('dashboard') )

                        else:
                            if guild.cache_time < time.time() or request.args.get('refresh') is not None:
                                channels = [x for x in api_get('guilds/{}/channels'.format(guild.guild)).json() if isinstance(x, dict) and x['type'] == 0]

                                ChannelData.query.filter((ChannelData.guild == guild_id) & ChannelData.channel.notin_([x['id'] for x in channels])).delete(synchronize_session='fetch')

                                for channel in channels:
                                    c = ChannelData.query.filter(ChannelData.channel == channel['id'])

                                    if c.count() > 0:
                                        ch = c.first()
                                        ch.name = channel['name']

                                    else:
                                        ch = ChannelData(channel=channel['id'], name=channel['name'], guild=guild_id)
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

                                guild.cache_time = time.time() + 10800 # 3 hour cache length

                            channels = [x.channel for x in guild.channels]
                            db.session.commit() # commit 

                            break

                else:
                    flash('You do not have permission to view this guild')
                    return redirect(url_for('dashboard'))

            guild = GuildData.query.filter(GuildData.guild == guild_id).first()
            server = Server.query.filter(Server.server == guild_id).first()
            reminders = Reminder.query.filter(Reminder.channel.in_([x for x in channels])).order_by(Reminder.time).all() # fetch reminders

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

        if request.args.get('refresh') is None:
            
            return render_template('dashboard.html',
                out=True,
                guilds=member.guilds,
                guild=None,
                server=None,
                member=member,
                time=time.time())

        else:
            return redirect( url_for('dashboard') )
