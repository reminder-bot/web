import io
import os

from flask import redirect, url_for, request, render_template

from app.models import User
from app import app
from . import LOGO_URL
from ..helpers import get_internal_id


@app.route('/cookies/')
def cookies():
    return render_template('cookies.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/help/')
def help_page():
    extra_command_properties = {
        '$natural': {
            'wiki': '/natural',

            'dashboard': True,
        },

        '$del': {
            'wiki': '/del',

            'dashboard': True,
        },

        '$look [n] [channel] [enabled] [time]': {
            'wiki': '/look',

            'dashboard': True,
        },

        '$remind [user/channel] <time-to-reminder> <message>': {
            'wiki': '/remind',

            'dashboard': True,
        },

        '$interval [user/channel] <time-to-reminder> <interval> <message>': {
            'wiki': '/interval',

            'dashboard': True,
        },

        '$offset': {
            'wiki': '/offset',

            'dashboard': False,
        },

        '$pause [time]': {
            'wiki': None,

            'dashboard': True,
        },

        '$restrict [role mention] [commands]': {
            'wiki': None,

            'dashboard': True,
        },

        '$blacklist [channel-name]': {
            'wiki': None,

            'dashboard': True,
        },

        '$todos': {
            'wiki': None,

            'dashboard': True,
        },

        '$todo server': {
            'wiki': None,

            'dashboard': True,
        },

        '$todo channel': {
            'wiki': None,

            'dashboard': True,
        },

        '$alias': {
            'wiki': None,

            'dashboard': True,
        },
    }

    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help_page'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html',
                           command_properties=extra_command_properties,
                           help=s['help_raw'],
                           languages=all_langs,
                           title='Help',
                           language=lang,
                           logo=LOGO_URL)


@app.route('/user-settings/')
def user_settings():
    member = User.query.get(get_internal_id())

    if member is None:
        return redirect(url_for('cache'))

    else:
        return render_template('user_settings.html',
                               guilds=member.permitted_guilds(),
                               guild=None,
                               member=member)
