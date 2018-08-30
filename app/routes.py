from flask import redirect, render_template, request, url_for, session, abort
from app import app, discord, db
from app.models import Server, Reminder, User
import os
import io
import requests
import json
from datetime import datetime
import time


@app.route('/')
@app.route('/help')
def help():
    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])
    print(all_langs)

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html', help=s['help_raw'], languages=all_langs, title='Help')


@app.route('/webhook', methods=['POST'])
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


@app.route('/oauth')
def oauth():
    if not discord.authorized:
        return redirect(url_for('discord.login'))

    return redirect(url_for('dashboard'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not discord.authorized:
        return redirect(url_for('oauth'))

    if request.method == 'POST':

        if request.form.get('update-server') is not None:

            server = Server.query.filter(Server.id == request.args.get('id')).first()

            p = request.form.get('prefix')

            if p is not None and len(p) <= 5:
                server.prefix = p

                db.session.commit()

        else:
            for index in range(len(session.get('reminders'))):
                try:
                    reminder_rewrite = [x for x in session.get('reminders') if x['index'] == index][0]
                except IndexError:
                    abort(400)

                if request.form.get('delete{}'.format(index)) is not None:

                    reminder = Reminder.query.get(reminder_rewrite['id'])

                    if reminder is not None:
                        db.session.delete(reminder)

                        db.session.commit()

                elif request.form.get('message{}'.format(index)) != reminder_rewrite['message']:

                    r = Reminder.query.get(reminder_rewrite['id'])
                    r.message = request.form.get('message{}'.format(index))

                    db.session.commit()

                if int(request.form.get('channel{}'.format(index))) != reminder_rewrite['channel'] and int(request.form.get('channel{}'.format(index))) in session['channels']:

                    r = Reminder.query.get(reminder_rewrite['id'])
                    r.channel = int(request.form.get('channel{}'.format(index)))

                    db.session.commit()

            new_msg = request.form.get('message_new')
            new_channel = request.form.get('channel_new')
            new_time = request.form.get('time_new')

            if new_msg and new_channel and new_time and int(new_channel) in session['channels']:
                reminder = Reminder(message=new_msg, time=new_time, channel=int(new_channel), interval=None)

                db.session.add(reminder)
                db.session.commit()

            try:
                session.pop('reminders')
            except KeyError:
                pass

        return redirect(url_for('dashboard', id=request.args.get('id')))

    else:
        r = []

        if request.args.get('refresh') == '1':
            session.pop('guilds')
            return redirect(url_for('dashboard'))

        if session.get('guilds') is None: # the code below is time-consuming; only run on first load and if the user wants to refresh the guild list.

            user = discord.get('api/users/@me').json()
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
                abort(403)

            reminders = Reminder.query.filter(Reminder.channel.in_([x['id'] for x in channels])).all()

            index = 0
            for reminder in reminders:
                r.append({})

                r[index]['message'] = reminder.message
                channel = [x for x in channels if int(x['id']) == reminder.channel][0]
                r[index]['channel'] = channel
                r[index]['time'] = [reminder.time, datetime.fromtimestamp(reminder.time).strftime('%d/%b/%Y %H:%M:%S')]
                r[index]['interval'] = reminder.interval
                r[index]['id'] = reminder.id
                r[index]['index'] = index

                index += 1

            session['reminders'] = r

            return render_template('dashboard.html', guilds=session['guilds'], reminders=session['reminders'], channels=channels, server=server, title='Dashboard')

        return render_template('dashboard.html', guilds=session['guilds'], reminders=[], channels=[], server=None, title='Dashboard')
