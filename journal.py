# -*- coding: utf-8 -*-

import os

# A library of stuff to use with "with", ie context.
from contextlib import closing

from flask import Flask

import psycopg2


DB_SCHEMA = """
DROP TABLE IF EXISTS entries;
CREATE TABLE entries (
    id serial PRIMARY KEY,
    title VARCHAR (127) NOT NULL,
    text TEXT NOT NULL,
    created TIMESTAMP NOT NULL
)
"""


# I still don't know what the significance of __name__ is here.
app = Flask(__name__)

# The value of the third string here called a libpq connection string.
app.config['DATABASE'] = os.environ.get(
    'DATABASE_URL', 'dbname=learning_journal user=fried'
)

def connect_db():
    ''' Return a connection to the configured database. '''

    return psycopg2.connect(app.config['DATABASE'])

def init_db():
    ''' Initialize the database using DB_SCHEMA.

    WARNING: Executing this function will drop existing tables. '''

    # with blocks clean up their context after execution
    # (( closing() is the context ))
    with closing(connect_db()) as db:

        db.cursor().execute(DB_SCHEMA)
        # Cursors do transactions.
        # Transactions must be committed before they take effect.
        db.commit()





@app.route('/')
def hello():
    # Ahh, non-unicode default string encoding... The joys of python 2.
    return u'Hello world!'

if __name__ == '__main__':

    app.run(debug=True)















