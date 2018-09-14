from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder, User
import os
import io
import requests
import json
from datetime import datetime
import time
import pytz


@app.route('/')
def index():
    return redirect( url_for('help') )

@app.route('/help/')
def help():
    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])
    print(all_langs)

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html', help=s['help_raw'], languages=all_langs, title='Help', logo='https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg')


@app.route('/webhook/', methods=['POST'], strict_slashes=False)
def webhook():
    print(request.json)

    user = User.query.filter_by(id=request.json['user']).first()

    if user is None:
        user = User(id=request.json['user'], last_vote=time.time())
        db.session.add(user)

    else:
        user.last_vote = time.time()

    db.session.commit()

    return '', 200


@app.route('/delete', strict_slashes=False)
def delete():

    reminder = Reminder.query.filter(Reminder.id == session['reminders'][int( request.args.get('index') )]['id'])
    reminder.delete(synchronize_session='fetch')

    db.session.commit()

    return '', 200


@app.route('/oauth/')
def oauth():
    if not discord.authorized:
        return redirect(url_for('discord.login'))

    return redirect(url_for('dashboard'))


@app.route('/dashboard/', methods=['GET', 'POST'])
def dashboard():
    if not discord.authorized:
        return redirect(url_for('oauth'))

    if request.method == 'POST':

        if request.form.get('update-server') is not None:

            server = Server.query.filter(Server.id == request.args.get('id')).first()

            p = request.form.get('prefix')

            if p is not None:
                if len(p) <= 5:
                    server.prefix = p

                    db.session.commit()

                elif p != '':
                    flash('There was an error setting your prefix.')

            tz = request.form.get('timezone')

            if tz is not None:
                if tz in pytz.all_timezones:
                    server.timezone = tz

                    db.session.commit()

                elif tz != '':
                    flash('There was an error setting your timezone.')

        else:
            for reminder in session['reminders']:
                if 'message_{}'.format(reminder['index']) in request.form.keys():

                    r = Reminder.query.get(reminder['id'])

                    channel = request.form.get('channel_{}'.format(reminder['index']))
                    message = request.form.get('message_{}'.format(reminder['index']))

                    if not 0 < len(message) < 200:
                        flash('Error setting reminder message (length wrong)')

                    elif channel not in [x['id'] for x in session['channels']]:
                        flash('Error setting reminder channel (channel not found)')

                    else:

                        r.message = message
                        r.channel = channel

                        db.session.commit()

                    break

            else:
                new_msg = request.form.get('message_new')
                new_channel = request.form.get('channel_new')
                new_time = request.form.get('time_new')

                if not all([x in '0123456789' for x in new_time]):
                    flash('Error setting reminder')

                elif int(new_time) - 1576800000 > time.time():
                    flash('Error setting reminder (time is too long)')

                elif new_msg and new_channel in [x['id'] for x in session['channels']]:

                    if not 0 < len(new_msg) < 200:
                        flash('Error setting reminder (message length wrong)')

                    else:
                        reminder = Reminder(message=new_msg, time=int(new_time), channel=int(new_channel), interval=None)

                        db.session.add(reminder)
                        db.session.commit()

                elif new_channel not in [x['id'] for x in session['channels']]:
                    flash('Error setting reminder (channel not found)')

            try:
                session.pop('reminders')
            except KeyError:
                pass

        return redirect(url_for('dashboard', id=request.args.get('id')))

    else:
        r = []

        user = discord.get('api/users/@me').json()

        if request.args.get('refresh') == '1':
            session.pop('guilds')
            return redirect(url_for('dashboard'))

        if session.get('guilds') is None: # the code below is time-consuming; only run on first load and if the user wants to refresh the guild list.

            guilds = discord.get('api/users/@me/guilds').json()

            user_id = user['id']

            available_guilds = []

            for guild in guilds:

                idx = guild['id']

                s = Server.query.filter_by(id=idx).first()

                if s is None:
                    continue

                restrictions = s.restrictions

                if (guild['permissions'] & 0x00002000) or (guild['permissions'] & 0x00000020) or (guild['permissions'] & 0x00000008):
                    available_guilds.append(guild)
                    continue

                elif restrictions['data'] == []:
                    continue

                member = requests.get('https://discordapp.com/api/v6/guilds/{}/members/{}'.format(idx, user_id), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()
                for role in member['roles']:
                    if int(role) in restrictions['data']:
                        available_guilds.append(guild)
                        break

            session['guilds'] = available_guilds

        if request.args.get('id') is not None:
            for guild in session['guilds']:
                if guild['id'] == request.args.get('id'):
                    server = Server.query.filter( Server.id == guild['id'] ).first()

                    channels = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/channels'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json() if x['type'] == 0]
                    session['channels'] = channels
                    break

            else:
                flash('You do not have permission to view this guild')
                return redirect(url_for('dashboard'))

            reminders = Reminder.query.filter(Reminder.channel.in_([x['id'] for x in channels])).all()

            index = 0
            for reminder in reminders:

                r.append({})

                r[index]['message'] = reminder.message
                channel = [x for x in channels if int(x['id']) == reminder.channel][0]
                r[index]['channel'] = channel
                r[index]['time'] = reminder.time
                r[index]['interval'] = reminder.interval
                r[index]['id'] = reminder.id
                r[index]['index'] = index

                index += 1

            session['reminders'] = r

            return render_template('dashboard.html', guilds=session['guilds'], reminders=session['reminders'], channels=channels, server=server, title='Dashboard', user=user, timezones=app.config['TIMEZONES'])

        return render_template('dashboard.html', guilds=session['guilds'], reminders=[], channels=[], server=None, title='Dashboard', user=user, timezones=app.config['TIMEZONES'])
