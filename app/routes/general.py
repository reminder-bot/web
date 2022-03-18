import io
import os

from flask import redirect, url_for, request, render_template

from app.models import User
from app import app
from . import LOGO_URL
from ..helpers import get_internal_id


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/help/')
def help():
    return redirect(url_for('index'))


@app.route('/cookies/')
def cookies():
    return render_template('cookies.html')


@app.route('/terms/')
def terms():
    return render_template('terms.html')


@app.route('/privacy/')
def privacy():
    return render_template('privacy.html')


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
