from flask import render_template, session

from app import app


@app.route('/cookies/')
def cookies():
    return render_template('cookies.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/help/')
def help_page():
    return render_template('help.html')


@app.route('/error')
def throw_error():
    return render_template('errors/500.html')


@app.errorhandler(500)
def internal_server_error(_error):
    session.clear()

    return render_template('errors/500.html')


@app.errorhandler(404)
def file_not_found(_error):
    session.clear()

    return render_template('errors/404.html')
