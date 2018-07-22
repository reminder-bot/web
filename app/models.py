from app import db
from sqlalchemy_json import NestedMutableJson, MutableJson


class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column( db.Integer, primary_key=True, unique=True)
    message = db.Column( db.Unicode(2000) )
    channel = db.Column( db.BigInteger )
    time = db.Column( db.BigInteger )
    interval = db.Column( db.Integer )

    mysql_charset = 'utf8mb4'

    def __repr__(self):
        return '<Reminder "{}" <#{}> {}s>'.format(self.message, self.channel, self.time)


class Server(db.Model):
    __tablename__ = 'servers'

    map_id = db.Column( db.Integer, primary_key=True)
    id = db.Column( db.BigInteger, unique=True)
    prefix = db.Column( db.String(5) )
    language = db.Column( db.String(2) )
    timezone = db.Column( db.String(30) )
    blacklist = db.Column( NestedMutableJson )
    restrictions = db.Column( NestedMutableJson )
    tags = db.Column( MutableJson )
    autoclears = db.Column( MutableJson )

    mysql_charset = 'utf8mb4'

    def __repr__(self):
        return '<Server {}>'.format(self.id)