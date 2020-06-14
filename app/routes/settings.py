from flask import request, abort, jsonify, redirect, url_for, render_template

from app import app, db
from app.models import User, Guild, CommandRestriction, CommandAlias
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
