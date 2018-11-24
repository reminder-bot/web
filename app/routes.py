from flask import redirect, render_template, request, url_for, session, abort, flash
from app import app, discord, db
from app.models import Server, Reminder
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

                    if r is None:
                        flash('Reminder not found. Please reload the page')

                    else:

                        channel = request.form.get('channel_{}'.format(reminder['index']))
                        message = request.form.get('message_{}'.format(reminder['index']))

                        if not 0 < len(message) <= 200 and session['roles'] != 2:
                            flash('Error setting reminder message (length wrong)')

                        elif not 0 < len(message) < 2000 and session['roles'] == 2:
                            flash('Error setting reminder message (length wrong)')

                        elif channel not in session['channels']:
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


                if session['roles'] > 0:
                    try:
                        new_interval = int(request.form.get('interval_new'))
                    except ValueError:
                        new_interval = None

                    else:
                        if new_interval == 0 or not bool(new_interval):
                            new_interval = None
                else:
                    new_interval = None


                if not all([x in '0123456789' for x in new_time]):
                    flash('Error setting reminder')

                elif int(new_time) - 1576800000 > time.time():
                    flash('Error setting reminder (time is too long)')

                elif new_msg and new_channel in session['channels']:

                    if not 0 < len(new_msg) <= 200 and session['roles'] != 2:
                        flash('Error setting reminder (message length wrong)')

                    elif not 0 < len(new_msg) < 2000 and session['roles'] == 2:
                        flash('Error setting reminder (message length wrong)')

                    elif new_interval is not None and not 8 < new_interval < 1576800000:
                        flash('Error setting reminder (interval timer is out of bounds)')

                    else:
                        reminder = Reminder(message=new_msg, time=int(new_time), channel=int(new_channel), interval=new_interval)

                        db.session.add(reminder)
                        db.session.commit()

                elif new_channel not in session['channels']:
                    flash('Error setting reminder (channel not found)')

            try:
                session.pop('reminders')
            except KeyError:
                pass

        return redirect(url_for('dashboard', id=request.args.get('id')))

    else:
        try:
            user = discord.get('api/users/@me').json()
        except:
            return redirect( url_for('oauth') )

        if session.get('guilds') is None or session.get('reminders') is None or session.get('roles') is None or session.get('channels') is None or request.args.get('refresh'):
            # the code below is time-consuming; only run on first load and if the user wants to refresh the guild list.

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
                    available_guilds.append({'id': guild['id'], 'name': guild['name']})
                    continue

                elif restrictions['data'] == []:
                    continue

                member = requests.get('https://discordapp.com/api/v6/guilds/{}/members/{}'.format(idx, user_id), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json()
                for role in member['roles']:
                    if int(role) in restrictions['data']:
                        available_guilds.append(guild)
                        break

            reminder_guild_member = requests.get('https://discordapp.com/api/v6/guilds/350391364896161793/members/{}'.format(user_id), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})
            if reminder_guild_member.status_code == 200:

                roles = list(set([int(x) for x in reminder_guild_member.json()['roles']]) & set(app.config['PATREON_ROLES']))
                session['roles'] = len(roles)

            else:
                session['roles'] = 0

            session['guilds'] = available_guilds

        if request.args.get('id') is not None:
            for guild in session['guilds']:
                if guild['id'] == request.args.get('id'):
                    server = Server.query.filter( Server.id == guild['id'] ).first()

                    channels = [x for x in requests.get('https://discordapp.com/api/v6/guilds/{}/channels'.format(guild['id']), headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])}).json() if isinstance(x, dict) and x['type'] == 0]

                    session['channels'] = [x['id'] for x in channels]
                    break

            else:
                flash('You do not have permission to view this guild')
                return redirect(url_for('dashboard'))

            reminders = Reminder.query.filter(Reminder.channel.in_([x['id'] for x in channels])).all()

            r = []
            s_r = []

            for index, reminder in enumerate(reminders):

                r.append({})
                s_r.append({})

                r[index]['message'] = reminder.message
                channel = [x for x in channels if int(x['id']) == reminder.channel][0]
                r[index]['channel'] = channel

                r[index]['time'] = reminder.time

                r[index]['interval'] = reminder.interval

                r[index]['id'] = reminder.id
                s_r[index]['id'] = reminder.id

                r[index]['index'] = index
                s_r[index]['index'] = index

                index += 1

            session['reminders'] = s_r

            return render_template('dashboard.html', guilds=session['guilds'], reminders=r, channels=channels, server=server, title='Dashboard', user=user, timezones=app.config['TIMEZONES'], patreon=session['roles'])

        return render_template('dashboard.html', guilds=session['guilds'], reminders=[], channels=[], server=None, title='Dashboard', user=user, timezones=app.config['TIMEZONES'], patreon=session['roles'])
