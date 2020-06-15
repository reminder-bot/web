import io
import os

from flask import redirect, url_for, request, render_template

from app import app

from . import LOGO_URL


@app.route('/')
def index():
    return redirect(url_for('help_page'))


@app.route('/help/')
def help_page():
    all_langs = sorted([s[-5:-3] for s in os.listdir(app.config['BASE_URI'] + 'languages') if s.startswith('strings_')])

    lang = request.args.get('lang') or 'EN'
    lang = lang.upper()

    if lang not in all_langs:
        return redirect(url_for('help_page'))

    with io.open('{}languages/strings_{}.py'.format(app.config['BASE_URI'], lang), 'r', encoding='utf8') as f:
        s = eval(f.read())

    return render_template('help.html', help=s['help_raw'], languages=all_langs, title='Help', language=lang,
                           logo=LOGO_URL)
