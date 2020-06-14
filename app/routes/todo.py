from flask import request, redirect, url_for, abort, jsonify, render_template

from app import app, db
from app.models import Guild, Todo, User, Channel
from app.helpers import get_internal_id


@app.route('/dashboard/todo/')
def todo_dashboard():
    if (guild_id := request.args.get('id')) is not None:
        member = User.query.get(get_internal_id())
        guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif guild not in member.permitted_guilds():
            return abort(403)

        else:
            todos = {}
            global_todos = []

            for todo in guild.todo_list:
                if todo.channel_id is None:
                    global_todos.append(todo)

                else:
                    if todos.get(todo.channel_id) is None:
                        todos[todo.channel] = [todo]

                    else:
                        todos[todo.channel].append(todo)

            return render_template('todo_dashboard/todo_dashboard.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   todos=todos,
                                   global_todos=global_todos)

    else:
        return redirect(url_for('dashboard'))


@app.route('/alter_todo/', methods=['DELETE', 'POST', 'PATCH'])
def alter_todo():
    if (guild_id := request.json.get('guild_id')) is not None:

        member = User.query.get(get_internal_id())

        if guild_id in [x.id for x in member.permitted_guilds()]:

            if request.method == 'POST':
                if (channel_id := request.json.get('channel_id')) is not None and \
                        (value := request.json.get('value')) is not None and \
                        0 < len(value) <= 2000:

                    if channel_id == -1:
                        todo = Todo(guild_id=guild_id, channel_id=None, user_id=member.id, value=value)

                        db.session.add(todo)
                        db.session.commit()

                        return jsonify({'id': todo.id})

                    else:
                        guild = Guild.query.get(guild_id)

                        if guild.channels.filter(Channel.id == channel_id).first() is not None:
                            todo = Todo(guild_id=guild_id, channel_id=channel_id, user_id=member.id, value=value)

                            db.session.add(todo)
                            db.session.commit()

                            return jsonify({'id': todo.id})

                        else:
                            abort(404)

                else:
                    abort(400)

            elif request.method == 'DELETE':
                if (channel_id := request.json.get('channel_id')) is not None and \
                        (todo_id := request.json.get('todo_id')) is not None:

                    if channel_id == -1:
                        channel_id = None

                    Todo.query \
                        .filter(Todo.id == todo_id) \
                        .filter(Todo.channel_id == channel_id) \
                        .filter(Todo.guild_id == guild_id) \
                        .delete(synchronize_session='fetch')

            else:  # request method is patch
                if (channel_id := request.json.get('channel_id')) is not None and \
                        (todo_id := request.json.get('todo_id')) is not None and \
                        (value := request.json.get('value')) is not None:

                    query = Todo.query \
                        .filter(Todo.id == todo_id) \
                        .filter(Todo.channel_id == channel_id) \
                        .filter(Todo.guild_id == guild_id)

                    if (todo := query.first()) is not None:
                        todo.value = value

                    else:
                        abort(404)

            db.session.commit()

            return '', 201

    else:
        abort(400)