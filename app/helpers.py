import requests

from flask import session, abort

from app import app, discord, db
from app.models import User, Channel


def get_internal_id():
    if (internal_id := session.get('internal_id')) is not None:
        return internal_id

    else:
        user_id = session.get('user_id')
        user_name = session.get('user_name')

        if user_id is None:
            user = discord.get('api/users/@me').json()

            print(user)

            try:
                user_id = int(user['id'])
                user_name = '{}#{}'.format(user['username'], user['discriminator'])

            except KeyError:
                return abort(403)

            else:
                session['user_id'] = user_id
                session['user_name'] = user_name

        user_record = User.query.filter(User.user == user_id).first()

        if user_record is not None:
            session['internal_id'] = user_record.id
            user_record.name = user_name

            return user_record.id

        else:
            user_record = User(
                user=user_id,
                channel=Channel(
                    channel=api_post('users/@me/channels', {'recipient_id': user_id}).json()['id']
                ),
                name=user_name
            )

            db.session.add(user_record)
            db.session.commit()

            return get_internal_id()


def api_get(endpoint):
    return requests.get('https://discord.com/api/v6/{}'.format(endpoint),
                        headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})


def api_post(endpoint, data):
    return requests.post('https://discord.com/api/v6/{}'.format(endpoint), json=data,
                         headers={'Authorization': 'Bot {}'.format(app.config['BOT_TOKEN'])})
