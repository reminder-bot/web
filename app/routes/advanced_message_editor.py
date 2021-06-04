import io

from flask import redirect, url_for, render_template, abort, flash, request, send_file

from app import app, db
from app.models import Reminder, User, Guild, Event, EmbedField
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
            return render_template('reminder_dashboard/advanced_message_editor/advanced_message_editor.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   message=reminder,
                                   reminder_uid=reminder_uid)


@app.route('/dashboard/update_message/<int:guild_id>/<reminder_uid>', methods=['POST'])
def update_message(guild_id: int, reminder_uid: str):
    reminder = Reminder.query.filter(Reminder.uid == reminder_uid).first_or_404()

    field = request.form.get
    fields = request.form.getlist

    if field('embedded') is not None:
        color = Color.decode(field('embed_color')[1:])

        if color.failed:
            flash('Invalid color')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

        else:
            footer_icon = icon if (icon := field('embed_footer_icon')).startswith('https://') else None
            image_url = icon if (icon := field('embed_image')).startswith('https://') else None
            thumbnail_url = icon if (icon := field('embed_thumbnail')).startswith('https://') else None

            reminder.embed_title = field('embed_title')
            reminder.embed_description = field('embed_description')
            reminder.embed_footer = field('embed_footer')
            reminder.embed_image_url = image_url
            reminder.embed_thumbnail_url = thumbnail_url
            reminder.embed_footer_url = footer_icon
            reminder.embed_color = color.color

            combined = enumerate(zip(fields('field_title[]'), fields('field_value[]'), fields('field_inline[]')))
            for count, (title, value, inline) in combined:
                if len(title) * len(value) == 0:
                    continue

                elif count >= 25:
                    break

                else:
                    if count < reminder.fields.count():
                        embed_field = reminder.fields[count]

                        embed_field.title = title
                        embed_field.value = value
                        embed_field.inline = inline == 'true'

                    else:
                        db.session.add(
                            EmbedField(
                                title=title,
                                value=value,
                                inline=inline == 'true',
                                reminder_id=reminder.id
                            )
                        )

    else:
        reminder.embed_title = ''
        reminder.embed_description = ''
        reminder.embed_footer = ''
        reminder.embed_image_url = ''
        reminder.embed_thumbnail_url = ''
        reminder.embed_footer_icon = ''
        reminder.embed_color = ''

    if field('attachment_provided') is not None:
        file = request.files['file']

        if file.content_length < 8 * 1024 * 1024 and len(file.filename) <= 260:
            reminder.attachment = file.read()
            reminder.attachment_name = file.filename

        else:
            flash('File is too large or file name is too long. '
                  'Please upload a maximum of 8MB, with up to 260 character filename')
            return redirect(url_for('advanced_message_editor', guild_id=guild_id, reminder_uid=reminder_uid))

    else:
        reminder.attachment = None
        reminder.attachment_name = None

    reminder.tts = field('tts') is not None
    reminder.content = field('message_content')

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
