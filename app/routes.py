from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder, Interval, User, PartialMember, GuildData, ChannelData
import os
import io
import requests
import json
import time
import random


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


@app.route('/delete', strict_slashes=False)
def delete():

    reminder = Reminder.query.filter(Reminder.hashpack == request.args.get('index'))
    reminder.delete(synchronize_session='fetch')

    db.session.commit()

    return '', 200


@app.route('/oauth/')
def oauth():

    session.clear()

    return redirect(url_for('discord.login'))


def get_webhook(channel: int):
    webhooks = requests.get('https://discordapp.com/api/v6/channels/{}/webhooks'.format(channel), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()
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


def create_hashpack(i1, i2): # misnomer- not actually a hash in any way, was originally going to be a hash but changed my mind
    m = i2
    while m > 0:
        i1 *= 10
        m //= 10
    
    bigint = i1 + i2
    full = hex(bigint)[2:]
    while len(full) < 64:
        full += random.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.')

    return full


def api_get(endpoint):
    return requests.get('https://discordapp.com/api/v6/{}'.format(endpoint), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


@app.route('/creminder', methods=['POST'])
def change_reminder():
    new_msg = request.form.get('message_new')
    new_channel = request.form.get('channel_new')
    new_time = request.form.get('time_new')

    new_interval = None
    embed = None
    avatar = None
    username = None

    username = request.form.get('username')
    if username is not None:
        if not (0 < len(username) <= 32):
            username = None

    if session.get('roles', 0) > 0:
        try:
            new_interval = int(request.form.get('interval_new'))
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

        if session['roles'] > 1:
            avatar = request.form.get('avatar')
            if not avatar or not avatar.startswith('http') or not '.' in avatar:
                avatar = None


    if not all([x in '0123456789' for x in new_time]):
        flash('Error setting reminder (form data malformed)')

    elif 0 < int(new_time) or int(new_time) > time.time() + 1576800000:
        flash('Error setting reminder (time is too long)')

    elif new_msg and new_channel in session['channels']:

        if not 0 < len(new_msg) < 2000:
            flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

        elif new_interval is not None and not 8 < new_interval < 1576800000:
            flash('Error setting reminder (interval timer is out of bounds)')

        else:
            wh = None

            index = request.args.get('index')

            if index is not None:
                rem = Reminder.query.filter(Reminder.hashpack == index).first()

                if rem is None:
                    flash('Error changing reminder: Reminder not found')

                else:
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
                        interval = Interval(reminder=rem.id, period=new_interval, position=rem.intervals.order_by(Interval.position.desc()).first().position + 1)
                        db.session.add(interval)

                    for interval in rem.intervals:
                        field = request.form.get('interval_{}'.format(interval.position))
                        if field is not None and all(x in '0123456789.' for x in field):
                            val = float(field)

                            if 8 < val < 1576800000:
                                interval.period = val

            else:
                if request.args.get('id') != '0':
                    webhook = get_webhook(new_channel)

                else:
                    webhook = None

                full = create_hashpack(int(new_channel), int(new_channel))

                reminder = Reminder(message=new_msg, hashpack=full, time=int(new_time), channel=int(new_channel), position=0 if new_interval is not None else None, embed=embed, method='dashboard', webhook=webhook, username=username, avatar=avatar)
                db.session.add(reminder)

                if new_interval is not None:
                    db.session.commit()

                    interval = Interval(reminder=reminder.id, period=new_interval, position=0)
                    db.session.add(interval)

            db.session.commit()

    elif new_channel not in session['channels']:
        flash('Error setting reminder (channel not found)')

    if request.args.get('redirect'):
        return redirect(url_for('dashboard', id=request.args.get('redirect')))
    else:
        return redirect(url_for('dashboard'))


@app.route('/dashboard/', methods=['GET', 'POST'])
def dashboard():
    if not discord.authorized:
        return redirect(url_for('oauth'))

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
                session.add(member)

            member.name = user['name']

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

            member.guilds = []

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
                            g = GuildData(guild=idx, name=guild['name'], cache_time=0)
                            session.add(g)
                            
                        member.guilds.append(g)
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
                            if guild.cache_time < time.time()
                                channels = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/channels'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json() if isinstance(x, dict) and x['type'] == 0]

                                ChannelData.query.filter(ChannelData.guild == guild_id & ChannelData.channel.notin_([x['id'] for x in channels])).delete(synchronize_session='fetch')

                                for channel in channels:
                                    c = ChannelData.query.filter(ChannelData.channel == channel['id'])

                                    if c.count() > 0:
                                        ch = c.first()
                                        ch.name = channel['name']

                                    else:
                                        ch = ChannelData(channel=channel['id'], name=channel['name'], guild=guild_id)
                                        session.add(ch)


                                members = api_get('guilds/{}/members?limit=150'.format(guild['id'])).json()

                                guild.members = []

                                for member in members:
                                    m = PartialMember.query.filter(PartialMember.user == member['user']['id']).first()

                                    if m is not None:
                                        m.name = member['user']['name']

                                    else:
                                        m = PartialMember(user=member['user']['id'], name=member['user']['name'])
                                        session.add(m)

                                    guild.members.append(m)


                                roles = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/roles'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()]

                                RoleData.query.filter(RoleData.guild == guild_id & RoleData.role.notin_([x['id'] for x in roles])).delete(synchronize_session='fetch')

                                for role in roles:
                                    c = RoleData.query.filter(RoleData.role == role['id'])

                                    if c.count() > 0:
                                        ch = c.first()
                                        ch.name = role['name']

                                    else:
                                        ch = RoleData(role=role['id'], name=role['name'], guild=guild_id)
                                        session.add(ch)

                            channels = [x.channel for x in guild.channels] # turn the channels into Ids 

                            break

                else:
                    flash('You do not have permission to view this guild')
                    return redirect(url_for('dashboard'))

            reminders = Reminder.query.filter(Reminder.channel.in_(channels)).order_by(Reminder.time).all() # fetch reminders

            for reminder in reminders: # assign channel names to all reminders
                for channel in channels:
                    if channel.channel == reminder.channel:
                        reminder.channel_name = channel.name
                        break

            return render_template('dashboard.html',
                out=False,
                guilds=member.guilds,
                reminders=reminders,
                channels=channels,
                members=members,
                roles=roles,
                server=server,
                user=user,
                time=time.time(),
                patreon=session['roles'])

        return render_template('dashboard.html',
            out=True,
            guilds=session['guilds'],
            reminders=[],
            channels=[],
            members=[],
            roles=[],
            server=None,
            user=user,
            time=time.time(),
            patreon=session['roles'])
