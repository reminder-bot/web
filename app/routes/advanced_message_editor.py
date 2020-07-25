import io

from flask import redirect, url_for, render_template, abort, flash, request, send_file

from app import app, db
from app.models import Reminder, User, Guild, Embed, Event
from app.helpers import get_internal_id
from app.color import Color


@app.route('/dashboard/ame/<int:guild_id>/<reminder_uid>', methods=['GET'])
def advanced_message_editor(guild_id: int, reminder_uid: str):
    member = User.query.get(get_internal_id())
    guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

    if member is None:
        return redirect(url_for('cache'))

    elif guild not in member.permitted_guilds():
        return abort(403)

    else:
        reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first()

        if reminder is None:
            return abort(404)

        else:
            return render_template('reminder_dashboard/advanced_message_editor.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   message=reminder.message,
                                   reminder_uid=reminder_uid)


@app.route('/dashboard/update_message/<int:guild_id>/<reminder_uid>', methods=['POST'])
def update_message(guild_id: int, reminder_uid: str):
    reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first_or_404()

    field = request.form.get

    if field('embedded') is not None:
        color = Color.decode(field('embed_color')[1:])

        if color.failed:
            flash('Invalid color')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

        else:
            footer_icon = icon if (icon := field('embed_footer_icon')).startswith('https://') else None
            image_url = icon if (icon := field('embed_image')).startswith('https://') else None
            thumbnail_url = icon if (icon := field('embed_thumbnail')).startswith('https://') else None

            reminder.message.embed = Embed(
                title=field('embed_title'),
                description=field('embed_description'),
                footer=field('embed_footer'),
                image_url=image_url,
                thumbnail_url=thumbnail_url,
                footer_icon=footer_icon,
                color=color.color)

    else:
        if reminder.message.embed is not None:
            db.session.delete(reminder.message.embed)

        reminder.message.embed = None

    if field('attachment_provided') is not None:
        file = request.files['file']

        if file.content_length < 8 * 1024 * 1024 and len(file.filename) <= 260:
            reminder.message.attachment = file.read()
            reminder.message.attachment_name = file.filename

        else:
            flash('File is too large or file name is too long. '
                  'Please upload a maximum of 8MB, with up to 260 character filename')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

    else:
        reminder.message.attachment = None
        reminder.message.attachment_name = None

    reminder.message.tts = field('tts') is not None

    reminder.message.content = field('message_content')

    Event.new_edit_event(reminder, get_internal_id())

    db.session.commit()

    return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))


@app.route('/download_attachment/<reminder_uid>')
def download_attachment(reminder_uid):
    reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first_or_404()

    if reminder is None or reminder.message.attachment is None:
        abort(404)
    else:
        return send_file(io.BytesIO(reminder.message.attachment), attachment_filename=reminder.message.attachment_name)
