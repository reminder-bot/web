from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder, Interval
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

    reminder = Reminder.query.filter(Reminder.id == session['reminders'][int( request.args.get('index') )]['id'])
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


def create_hashpack(self, i1, i2):
    m = i2
    while m > 0:
        i1 *= 10
        m //= 10
    
    bigint = i1 + i2
    full = hex(bigint)[2:]
    while len(full) < 64:
        full += random.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')

    return full


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

    elif int(new_time) - 1576800000 > time.time():
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
                    rem.username = username or 'Reminder'
                    rem.avatar = avatar or 'https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg'

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

    try:
        session.pop('reminders')
    except:
        pass

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

        if any([session.get(x) is None for x in ('guilds', 'roles', 'channels')]) or request.args.get('refresh'):
            # the code below is time-consuming; only run on first load and if the user wants to refresh the guild list.
            guilds = discord.get('api/users/@me/guilds').json()

            user_id = user['id']

            available_guilds = []

            for guild in guilds:

                idx = guild['id']

                s = Server.query.filter_by(server=idx).first()

                if s is None:
                    continue

                if (guild['permissions'] & 0x00002000) or (guild['permissions'] & 0x00000020) or (guild['permissions'] & 0x00000008):
                    available_guilds.append({'id': guild['id'], 'name': guild['name']})
                    continue

            reminder_guild_member = requests.get('https://discordapp.com/api/v6/guilds/{}/members/{}'.format(app.config['PATREON_SERVER'], user_id), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})
            if reminder_guild_member.status_code == 200:

                roles = list(set([int(x) for x in reminder_guild_member.json()['roles']]) & set(app.config['PATREON_ROLES']))
                session['roles'] = len(roles)

            else:
                session['roles'] = 0

            session['guilds'] = available_guilds

        if request.args.get('id') is not None:
            for guild in session['guilds']:
                if guild['id'] == request.args.get('id'):
                    server = Server.query.filter( Server.server == guild['id'] ).first()

                    channels = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/channels'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json() if isinstance(x, dict) and x['type'] == 0]

                    session['channels'] = [x['id'] for x in channels]

                    members = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/members?limit=50'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()]

                    roles = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/roles'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()]
                    break

                elif request.args.get('id') == '0':
                    server = None

                    channels = [requests.post('https://discordapp.com/api/v6/users/@me/channels', json={'recipient_id': user['id']}, headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()]
                    session['channels'] = [x['id'] for x in channels]

                    members = []
                    roles = []
                    break

            else:
                flash('You do not have permission to view this guild')
                return redirect(url_for('dashboard'))

            reminders = Reminder.query.filter(Reminder.channel.in_(session['channels'])).order_by(Reminder.time).all()

            r = []

            for index, reminder in enumerate(reminders):

                r.append({})

                r[index]['message'] = reminder.message
                channel = [x for x in channels if int(x['id']) == reminder.channel][0]
                r[index]['channel'] = channel
 
                r[index]['username'] = reminder.username or 'Reminder'
                r[index]['avatar'] = reminder.avatar

                r[index]['time'] = reminder.time

                period = None

                if reminder.position is not None:
                    i = Interval.query.filter(Interval.reminder == reminder.id).first()
                    period = i.period

                r[index]['interval'] = period

                r[index]['embed'] = hex(reminder.embed).strip('0x') if reminder.embed is not None else '00A65A'
                r[index]['embedded'] = not (reminder.embed is None)

                r[index]['avatar'] = reminder.avatar or 'https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg'

                r[index]['id'] = reminder.id

                r[index]['index'] = reminder.hashpack

            return render_template('dashboard.html',
                out=False,
                guilds=session['guilds'],
                reminders=r,
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
