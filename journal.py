# -*- coding: utf-8 -*-

import os
import datetime

# A library of stuff to use with "with", ie context.
from contextlib import closing


from flask import Flask
from flask import render_template
from flask import abort
from flask import request
from flask import url_for
from flask import redirect

# for cookie handling: admin
from flask import session

# g is a "local global" Flask provides.
# This just means it's an object that stores state to pass between funx.
# It's a grab bag object.
# I would have architected this to use a purpose-named class, such as
# "DatabaseConnector" or something, to keep the various state types
# separate from each other, but maybe that's too much overhead?
# I don't know if it's better to namespace every piece of conceptually
# distinct state or just toss it all in one big box like this...
from flask import g


import psycopg2

# pip needs to install and freeze this.
# Fortunately, I've now completed that.
# reference: http://pythonhosted.org/passlib/
from passlib.hash import pbkdf2_sha256


DB_SCHEMA = """
DROP TABLE IF EXISTS entries;
CREATE TABLE entries (
    id serial PRIMARY KEY,
    title VARCHAR (127) NOT NULL,
    text TEXT NOT NULL,
    created TIMESTAMP NOT NULL
)
"""

# "Although the %s placeholders in the SQL look like string formatting,
# they are not.
# Parameters passed this way are properly escaped and safe from
# SQL injection.
# Only ever use this form to parameterize SQL queries in Python.
# NEVER USE PYTHON STRING FORMATTING WITH A SQL STRING."

DB_ENTRY_INSERT = """
INSERT INTO entries (title, text, created) VALUES (%s, %s, %s)
"""

DB_ENTRIES_LIST = """
SELECT id, title, text, created FROM entries ORDER BY created DESC
"""


# I still don't know what the significance of __name__ is here.
app = Flask(__name__)

# The value of the third string here is called a libpq connection string.
app.config['DATABASE'] = os.environ.get(
    'DATABASE_URL', 'dbname=learning_journal user=fried'
)

# "You could implement an entire database table for
# the purpose of storing your user information, but really that’s
# overkill for a system that only has one user.
# You should never implement more code than you need."

# "So how can you solve the problem of storing the data
# needed to authenticate a user?"

# "How about configuration?"
app.config['ADMIN_USERNAME'] = os.environ.get(
    'ADMIN_USERNAME', 'admin'
)

# "Because you are using the same pattern for this configuration as for
# the database connection string, you’ll be able to use
# Environment Variables on your Heroku machine to store the username
# and password for your live site in a reasonably secure fashion."
app.config['ADMIN_PASSWORD'] = os.environ.get(
    'ADMIN_PASSWORD', pbkdf2_sha256.encrypt('admin')
)

# "Flask will not allow using the session without having
# a secret key configured. This key is used to perform
# the encryption of the cookie sent back to the user.
# Preventing you from using a session without one is
# a good example of secure by default."
app.config['SECRET_KEY'] = os.environ.get(
    'FLASK_SECRET_KEY', 'sooperseekritvaluenooneshouldknow'
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


def get_database_connection():

    # If this was implemented with keyword arguments, it would be
    # easier to understand.
    # g appears to be a flask-native object whose purpose is to hold
    # connections and pass them between functions without using return.
    # That is what they mean by "local globals," I think.
    # What this assignment is doing is:
    # 1. Fetching the flask.g object
    # 2. Returning its 'db' attribute
    # 3. Using None as the default value (I think)
    db = getattr(g, 'db', None)

    # This part creates a database connection if None exists and
    # assigns it to flask.g so it sticks around in global scope under
    # the aegis of that wandering object.
    # I think the g stands for "global".
    if db is None:
        # Remember, g comes from the flask library.
        g.db = db = connect_db()

    # If flask.g has a db in it, that db is passed to whatever called
    # get_database_connection() here.
    # If flask.g has no db in it, this makes a new connection and
    # passes it to whatever called get_database_connection() here.
    return db


# Teardown requests happen after the execution of a full
# HTTP request-reponse cycle, even if the response is precluded by
# an unhandled exception.
@app.teardown_request
def teardown_request(exception):

    # How Flask wants me to shuttle global scope around.
    # It feels like pulling state out of a bag.
    db = getattr(g, 'db', None)

    # Wait, why is this check being done outside of
    # get_database_connection()? Can teardown_request() be called when
    # there is no database and there isn't supposed to be a database?
    if db is not None:

        # Wow, I missed this line for two or three days.
        if exception and isinstance(exception, psycopg2.Error):

            # "if there was a problem with the database, rollback any
            # existing transaction"
            # So teardown_request should never make a database connection,
            # only clean up existing ones or save the database state. OK.
            db.rollback()

        else:

            db.commit()

        # This will shut down the db connection inside flask.g, too, if I
        # understand correctly.
        # It looks like HTTP request-response cycles make a connection,
        # do stuff in it, and then call teardown_request() to ensure it's
        # handled cleanly.
        # Though I could be wrong about that.
        db.close()


def write_entry(title, text):

    if not title or not text:
        raise ValueError(
            "Title and text are both required for writing an entry.")

    con = get_database_connection()
    cur = con.cursor()

    # "It is best practice to store time values in UTC."
    now = datetime.datetime.utcnow()

    # Note that the set-as-required-in-psql parameter for
    # the "created" database field is not supplied to write_entry().
    # Instead, it's dynamically generated inside this Python and
    # provided to the database at the time of the HTTP request, making
    # the resulting journal entry a chimaera of
    # HTTP, Python, and PSQL.
    # (not counting the fathomless depths beneath our top level code)
    cur.execute(DB_ENTRY_INSERT, [title, text, now])


def get_all_entries():

    ''' Return a list of all entries as dictionaries. '''

    con = get_database_connection()
    cur = con.cursor()
    cur.execute(DB_ENTRIES_LIST)

    keys = ('id', 'title', 'text', 'created')

    # List comprehension, dictionary compilation, zippitude
    return [dict(zip(keys, row)) for row in cur.fetchall()]

    # "Get all results with cursor.fetchall().
    # Get n results with cursor.fetchmany(size=n).
    # Get one result with cursor.fetchone()."


@app.route('/')
def show_entries():

    entries = get_all_entries()

    # Kwargs shouldn't be named identically to variable names, should they?
    return render_template('list_entries.html', entries=entries)


# Is this out of order? Should it be above the '/' route due to
# first full string match search?
# ... apparently not, it's actually most-complete-string-match, I guess.
@app.route('/add', methods=['POST'])
def add_entry():

    try:
        write_entry(request.form['title'], request.form['text'])

    except psycopg2.Error:

        # This is from Flask: an HTTP error response.
        abort(500)

    # Sends you to the show_entries() view.
    # flask.url_for() sends up the view function named its argument string.
    return redirect(url_for('show_entries'))


def do_login(username='', passwd=''):

    # "Do not distinguish between a bad password and a bad username.
    # To do so is to leak sensitive information.
    # Do not store more information
    # than is absolutely required in a session."

    if username != app.config['ADMIN_USERNAME']:

        raise ValueError

    # The other half of the passlib API:
    if not pbkdf2_sha256.verify(passwd, app.config['ADMIN_PASSWORD']):

        raise ValueError

    session['logged_in'] = True


@app.route('/login', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        try:

            do_login(request.form['username'].encode('utf-8'),
                     request.form['password'].encode('utf-8'))

        except ValueError:

            error = "Login Failed"

        else:

            return redirect(url_for('show_entries'))

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():

    session.pop('logged_in', None)

    return redirect(url_for('show_entries'))


if __name__ == '__main__':

    # The run() command must always be the last thing in the file.
    app.run(debug=True)
