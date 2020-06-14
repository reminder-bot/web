import itertools

from flask import redirect, url_for, render_template, abort, request

from app import app
from app.models import User, Event, Guild
from app.helpers import get_internal_id


@app.route('/dashboard/audit_log')
def audit_log():
    class PseudoEvent:
        def __init__(self, reminder):
            self.event_name = 'create'
            self.bulk_count = None
            self.user = User.query.get(reminder.set_by)
            self.time = reminder.set_at
            self.reminder = reminder

    def combine(a, b):
        out = []

        while len(a) * len(b) > 0:
            if a[0].time > b[0].time:
                out.append(a.pop(0))
            else:
                out.append(b.pop(0))

        if len(a) > 0:
            out.extend(a)

        else:
            out.extend(b)

        return out

    if (guild_id := request.args.get('id')) is not None:
        member = User.query.get(get_internal_id())
        guild = Guild.query.filter(Guild.guild == guild_id).first_or_404()

        if member is None:
            return redirect(url_for('cache'))

        elif guild not in member.permitted_guilds():
            return abort(403)

        else:
            events = Event.query.filter(Event.guild_id == guild.id).order_by(Event.time.desc())
            pseudo_events = [PseudoEvent(r) for r in itertools.chain(*[c.reminders for c in guild.channels])]

            all_events = combine(events.all(), pseudo_events)

            return render_template('audit_log/audit_log.html',
                                   guilds=member.permitted_guilds(),
                                   guild=guild,
                                   member=member,
                                   events=all_events)

    else:
        return redirect(url_for('dashboard'))
