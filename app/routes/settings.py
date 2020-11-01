from flask import request, abort, jsonify, redirect, url_for, render_template

from app import app, db
from app.models import User, Guild, CommandRestriction, CommandAlias, Channel
from app.helpers import get_internal_id


@app.route('/dashboard/settings/')
def settings_dashboard():
    if (guild_id := request.args.get('id')) is not None:
        member = User.query.get(get_internal_id())
        guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif guild not in member.permitted_guilds():
            return abort(403)

        else:
            return render_template('settings_dashboard/settings_dashboard.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   command_restrictions=guild.command_restrictions)

    else:
        return redirect(url_for('dashboard'))


@app.route('/change_restrictions/', methods=['PATCH'])
def change_restrictions():
    if (guild_id := request.json.get('guild_id')) and \
            (command := request.json.get('command')) and \
            (roles := request.json.get('roles')) is not None:

        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:
            guild = Guild.query.get(guild_id)

            guild.command_restrictions.filter(CommandRestriction.command == command).delete(synchronize_session='fetch')

            valid_ids = [r.id for r in guild.roles]

            for role in filter(lambda r: int(r) in valid_ids, roles):
                c = CommandRestriction(role_id=role, guild_id=guild_id, command=command)
                db.session.add(c)

            db.session.commit()

            return '', 201

        else:
            abort(403)

    else:
        abort(400)


@app.route('/change_aliases/', methods=['POST', 'DELETE'])
def change_aliases():
    if (guild_id := request.json.get('guild_id')) is not None:

        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:

            if request.method == 'POST':
                if (command := request.json.get('command')) is not None and \
                        (name := request.json.get('name')) is not None:

                    if 1 < len(command) < 2048 and len(name) < 12:
                        if (alias_id := request.json.get('id')) is not None and \
                                (alias := CommandAlias.query.filter_by(guild_id=guild_id,
                                                                       id=alias_id).first()) is not None:

                            if name != alias.name and CommandAlias.query.filter_by(guild_id=guild_id,
                                                                                   name=name).first() is not None:
                                return 'Name must be unique', 400

                            else:
                                alias.name = name
                                alias.command = command

                        else:
                            if CommandAlias.query.filter_by(guild_id=guild_id, name=name).first() is not None:
                                return 'Name must be unique', 400

                            else:
                                alias = CommandAlias(name=name, command=command, guild_id=guild_id)

                                db.session.add(alias)
                                db.session.commit()

                                return jsonify({'id': alias.id, 'name': alias.name, 'command': alias.command})

                    else:
                        return 'Invalid input lengths', 400

                else:
                    abort(400)

            else:  # method is delete
                if (alias_id := request.json.get('id')) is not None:
                    CommandAlias.query.filter_by(guild_id=guild_id, id=alias_id).delete(synchronize_session='fetch')

                else:
                    abort(400)

            db.session.commit()

            return '', 201

        else:
            abort(400)

    else:
        abort(400)


@app.route('/change_blacklist/', methods=['POST', 'DELETE'])
def change_blacklist():
    if (guild_id := request.json.get('guild_id')) is not None and \
            (channel_id := request.json.get('channel_id')) is not None:

        member = User.query.get(get_internal_id())
        guild = Guild.query.get(guild_id)
        channel = Channel.query.get(channel_id)

        if guild in member.permitted_guilds() and channel in guild.channels:

            if request.method == 'POST':
                channel.blacklisted = True

            else:  # method is delete
                channel.blacklisted = False

            db.session.commit()

            return '', 201

        else:
            abort(400)

    else:
        abort(400)


@app.route('/default_values/', methods=['POST'])
def default_values():
    if (guild_id := request.json.get('guild_id')) is not None:
        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:
            if (username := request.json.get('username')) is not None and \
                    (avatar := request.json.get('avatar')) is not None:

                if 0 < len(username) < 32 and 0 < len(avatar) < 512:
                    channel = request.json.get('channel')

                    guild = Guild.query.get(guild_id)

                    guild.default_channel = Channel.query.get(channel)
                    guild.default_username = username
                    guild.default_avatar = avatar

                    db.session.commit()

                    return '', 201

                else:
                    abort(400)

        else:
            abort(403)

    else:
        abort(400)
