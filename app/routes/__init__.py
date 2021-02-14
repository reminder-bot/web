import typing

from flask import session, redirect, url_for
from app import app


MAX_TIME = 1576800000
MIN_INTERVAL = 60
LOGO_URL = 'https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg'


@app.errorhandler(500)
def internal_error(_error):
    session.clear()
    return "An error has occurred! We've made a report, and cleared your session cache on this website. If you " \
           "encounter this error again, please send us a message on Discord!"


@app.route('/oauth/')
def oauth():
    session.clear()

    return redirect(url_for('discord.login'))


@app.route('/cache/', methods=['GET'])
def cache():
    def check_user_patreon(checking_user: User) -> int:
        reminder_guild_member = api_get('guilds/{}/members/{}'.format(app.config['PATREON_SERVER'], checking_user.user))

        if reminder_guild_member.status_code == 200:
            roles = [int(x) for x in reminder_guild_member.json()['roles']]
            return any([x in roles for x in app.config['PATREON_ROLES']])

        else:
            return 0

    def get_user_guilds() -> list:

        def form_cached_guild(data: dict) -> Guild:
            guild_query = Guild.query.filter(Guild.guild == data['id'])

            if (guild_data := guild_query.first()) is not None:
                guild_data.name = data['name']

                return guild_data

        guilds: list = discord.get('api/users/@me/guilds').json()
        cached_guilds: list = []

        for guild in guilds:

            if guild['owner'] or guild['permissions'] & 0x00002028:
                cached_guild: typing.Optional[Guild] = form_cached_guild(guild)

                if cached_guild is not None:
                    cached_guilds.append(cached_guild)

        return cached_guilds

    if not discord.authorized:
        return render_template('dashboard_error.html', error_message='You must Authorize with Discord OAuth to '
                                                                     'use the web dashboard.')
    else:
        user: dict = discord.get('api/users/@me').json()

        user_id: int = int(user['id'])
        user_name: str = '{}#{}'.format(user['username'], user['discriminator'])

        session['user_id'] = user_id

        user_query = User.query.filter(User.user == user_id)
        cached_user: typing.Optional[User] = user_query.first()

        if cached_user is None:
            user_record = User(
                user=user_id,
                channel=Channel(
                    channel=api_post('users/@me/channels', {'recipient_id': user_id}).json()['id']
                ),
                name=user_name
            )

            db.session.add(user_record)

        else:
            session['internal_id'] = cached_user.id

            cached_user.name = user_name

            cached_user.patreon = check_user_patreon(cached_user) > 0

            cached_user.set_permitted_guilds(get_user_guilds())

        db.session.commit()

        return redirect(url_for('dashboard'))


from .general import *
from .reminder import *
from .settings import *
from .todo import *
from .advanced_message_editor import *
from .audit_log import *
