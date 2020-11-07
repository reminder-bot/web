from time import time as unix_time

from flask import request, jsonify, redirect, url_for, flash, render_template, abort

from app import app, db, discord
from app.models import Reminder, Event, Channel, Message, Guild, User, Role
from app.helpers import get_internal_id, api_post, api_get

from . import MIN_INTERVAL, MAX_TIME


@app.route('/dashboard/', methods=['GET'])
def dashboard():
    def permitted_access(accessing_guild: Guild):
        # if user wants to refresh the guild's data
        if request.args.get('refresh') is not None:
            print('Refreshing guild data for {}'.format(accessing_guild.guild))

            try:
                guild_channels = [x for x in api_get('guilds/{}/channels'.format(accessing_guild.guild)).json() if
                                  isinstance(x, dict) and x['type'] in (0, 5)]

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


@app.route('/delete_reminder/', methods=['POST'])
def delete_reminder():
    reminder_q = Reminder.query.filter(Reminder.uid == request.json['uid'])
    reminder = reminder_q.first()

    if reminder is not None:
        if reminder.channel.guild_id is not None:
            event = Event(event_name='delete', guild_id=reminder.channel.guild_id, user_id=get_internal_id())
            db.session.add(event)

        reminder_q.delete(synchronize_session='fetch')

        db.session.commit()

        return '', 200

    else:
        abort(404)


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

        if 0 < len(username) <= 32:
            reminder.username = username

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        elif 0 <= len(username):
            reminder.username = None

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

        if 0 < len(avatar) <= 512:
            reminder.avatar = avatar

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        elif 0 <= len(avatar):
            reminder.avatar = None

            db.session.commit()

            return '', 200

        else:
            return 'Avatar URL too long. Please use a maximum of 512 characters', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_channel/', methods=['POST'])
def change_channel():
    if (reminder := Reminder.query.filter(Reminder.uid == request.json['uid']).first()) is not None:

        if (channel := Channel.query.get(int(request.json['channel']))) is not None:

            if (channel.webhook_id or channel.webhook_token) is None:
                channel.update_webhook(api_get, api_post, app.config['DISCORD_OAUTH_CLIENT_ID'])

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

        if new_time is not None and 0 < new_time < unix_time() + MAX_TIME:
            reminder.time = new_time

            Event.new_edit_event(reminder, get_internal_id())

            db.session.commit()

            return '', 200

        elif new_time < 0:
            return 'Time cannot be less than zero', 400

        elif new_time > unix_time() + MAX_TIME:
            return 'Time must be less than {} seconds in the future'.format(MAX_TIME), 400

        elif new_time is None:
            return 'Something went wrong with client-side time processing. Please refresh the page', 400

        else:
            return 'This error should never happen, but something went wrong', 400

    else:
        return 'Reminder not found', 404


@app.route('/change_paused/', methods=['POST'])
def change_paused():
    if (guild_id := request.json.get('guild_id')) is not None and \
            (channel_id := request.json.get('channel_id')) is not None and \
            (pause := request.json.get('paused')) is not None:

        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:
            channel = Channel.query.get(channel_id)

            if channel is not None and channel.guild_id == guild_id:
                channel.paused = pause
                db.session.commit()

                return '', 201

            else:
                abort(404)

        else:
            abort(403)

    else:
        abort(400)


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


@app.route('/creminder', methods=['POST'])
def change_reminder():
    def end():
        if request.args.get('redirect'):
            return redirect(url_for('dashboard', id=request.args.get('redirect')))

        else:
            return redirect(url_for('dashboard'))

    member = User.query.get(get_internal_id())
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
            username = request.form.get('username') or 'Reminder'
            if not (0 < len(username) <= 32):
                username = None

            avatar = request.form.get('avatar')
            if not isinstance(avatar, str) or not avatar.startswith('http'):
                avatar = None

            new_interval = None
            if member.patreon:
                try:
                    new_interval = int(request.form.get('interval_new')) * int(request.form.get('multiplier_new'))

                except:
                    new_interval = None

            if not (0 < new_time < unix_time() + MAX_TIME):
                flash('Error setting reminder (time is too long)')

            elif new_channel == -1 or new_channel in [x.id for x in guild.channels]:

                if new_msg is not None and not 0 < len(new_msg) < 2048:
                    flash('Error setting reminder (message length wrong: maximum length 2000 characters)')

                elif new_interval is not None and not MIN_INTERVAL < new_interval < MAX_TIME:
                    flash('Error setting reminder (interval timer is out of range 800s < t < 50yr)')

                else:
                    if new_channel != -1:
                        channel = Channel.query.get(new_channel)

                        if channel is None:
                            abort(404)

                        elif (channel.webhook_id or channel.webhook_token) is None:
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
