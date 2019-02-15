from app import db

class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column( db.Integer, primary_key=True, unique=True )
    hashpack = db.Column( db.String(64), unique=True )
    message = db.Column( db.String(2000) )
    channel = db.Column( db.BigInteger )
    time = db.Column( db.BigInteger )
    position = db.Column( db.Integer )

    webhook = db.Column( db.String(256) )
    avatar = db.Column( db.String(512), default="https://raw.githubusercontent.com/reminder-bot/logos/master/Remind_Me_Bot_Logo_PPic.jpg", nullable=False )
    username = db.Column( db.String(32), default="Reminder", nullable=False )

    method = db.Column( db.Text )
    embed = db.Column( db.Integer, nullable=True )

    intervals = db.relationship('Interval', backref='r', lazy='dynamic')

    channel_name = 'unknown'


class Interval(db.Model):
    __tablename__ = 'intervals'

    id = db.Column( db.Integer, primary_key=True, unique=True)

    reminder = db.Column(db.Integer, db.ForeignKey('reminders.id'))

    period = db.Column(db.Integer)
    position = db.Column(db.Integer)


class Server(db.Model):
    __tablename__ = 'servers'

    id = db.Column( db.Integer, primary_key=True )
    server = db.Column( db.BigInteger, unique=True )
    prefix = db.Column( db.String(5), default="$", nullable=False )
    language = db.Column( db.String(2), default="EN", nullable=False )
    timezone = db.Column( db.String(30), default="UTC", nullable=False )
