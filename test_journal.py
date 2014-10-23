import contextlib  # closing

import pytest

from journal import app
from journal import connect_db
from journal import get_database_connection
from journal import init_db

# The walkthrough implied this manages browser cookies when used...
from flask import session

TEST_DSN = 'dbname=test_learning_journal user=fried'

SUBMIT_BTN = '<input type="submit" value="Share" name="Share"/>'


# Used for testing isolation. The wipe half of reinitting the database.
def clear_db():

    # This ensures the connection is closed later.
    # Context library is all for this kind of context stuff.
    with contextlib.closing(connect_db()) as db:

        # Testing is not supposed to be used with a deployed database,
        # apparently. That's where TEST_DSN's specification comes in:
        # This will all be done in the test_learning_journal db.
        # ...
        # NOTE: This database must be created manually on the CLI.
        # Done with:
        # createdb test_learning_journal
        db.cursor().execute("DROP TABLE entries")
        db.commit()


@pytest.fixture(scope='session')
def test_app():

    ''' Configure the app for use in testing. '''

    # What test_app() will do here is access the testing database
    # (which is created outside of my python, on the CLI (for now))

    # Flask apps have config dictionaries in them by design.
    app.config['DATABASE'] = TEST_DSN
    app.config['TESTING'] = True


# "The fixture function is defined with parameters.
# The names of the parameters must match registered fixtures.
# The fixtures named as parameters will be run surrounding the new fixture."
@pytest.fixture(scope='session')
def db(test_app, request):

    ''' Initialize the entries table and drop it when finished. '''

    # This is the "fixture function" with its "registered fixture" parameters.
    # The request parameter is a fixture that pytest gives you; you use it
    # to connect the cleanup() function to the db fixture.

    init_db()

    # Unexplained methods: cleardb addfinalizer cleanup

    # "The request parameter is a fixture that pytest registers.
    # You use it to connect the cleanup function to the db fixture.
    # This means that cleanup will be run after tests are complete
    # as a tear-down action."
    def cleanup():
        clear_db()

    # I THINK @app.teardown_request is a finalizer? Maaaaybe... ???
    request.addfinalizer(cleanup)


# This one makes helps tests run in isolation from each other.
# Specifically it makes a generator function fixture.
# This is critical because generators preserve internal state.
# As a result, "the entire test happens inside context manager scope"
@pytest.yield_fixture(scope='function')
def req_context(db):

    ''' Run tests within a test request context so that 'g' is present. '''

    # Wait... flask.g would not be available if we didn't make this
    # "request context" function?

    with app.test_request_context('/'):

        # First, yield nothing.
        # Wat.
        yield

        con = get_database_connection()
        con.rollback()

        # "Flask creates g when a cycle begines, but tests
        # have no request/response cycle.
        # Flasks's app.test_request_context is a "context provider".
        # Used in a with statement, it creates a mock request/response cycle."
        # ...
        # What this means is, there's no web server running to test this,
        # BUT we can simulate what would happen if there was.. by calling
        # appname.app.test_request_context()

        # "The request only exists inside the with block, so the
        # callback pattern used in the db fixture would not work."
        # I think that is referring to the request.addfinalizer(cleanup)
        # line?

        # "Because yield preserves internal state, the entire test
        # happens inside the context manager scope"
        # "When control returns to the fixture, code after the yield
        # statement is executed as the tear-down action."


# Now begins the testing of the database schema.
def run_independent_query(query, params=[]):

    # This function simply formalizes what I've been doing all along
    # to make DB queries inside Python.

    con = get_database_connection()
    cur = con.cursor()

    cur.execute(query, params)

    return cur.fetchall()


def test_write_entry(req_context):

    from journal import write_entry

    expected = ("My Title", "My Text")

    # Remember, star args are just how you unpack things.
    # ((double star args unpack things into a dict.))
    write_entry(*expected)

    # "run_independent_query() is a 'helper function' you can re-use."
    # Where's it come from, pytest? By way of the decorator??
    rows = run_independent_query("SELECT * FROM entries")

    # Huh, so this is just assertEquals... from pytest?
    # Maybe not, since it's its own freestanding operation?
    assert len(rows) == 1

    for val in expected:

        assert val in rows[0]

def test_edit_entry(req_context):

    from journal import edit_entry

    expected = ("")



def test_get_all_entries_empty(req_context):

    from journal import get_all_entries

    entries = get_all_entries()

    assert len(entries) == 0


def test_get_all_entries(req_context):

    from journal import get_all_entries, write_entry

    expected = ("My Title", "My Test")

    write_entry(*expected)

    entries = get_all_entries()

    assert len(entries) == 1

    for entry in entries:

        assert expected[0] == entry['title']
        assert expected[1] == entry['text']
        assert 'created' in entry


def test_empty_listing(db):

    # "app.test_client() returns a mock HTTP client,
    # like a web browser for development."
    # "Because this test actually creates a request, we don't need to use
    # the req_context fixture. Having an initialized database is enough"
    # "The data attribute of the response returned by client.get()
    # holds the full rendered HTML of our page."
    actual = app.test_client().get('/').data
    expected = 'No entries here so far'
    assert expected in actual


@pytest.fixture(scope='function')
def with_entry(db, request):

    from journal import write_entry

    expected = (u'Test Title)', u'Test Text')

    with app.test_request_context('/'):

        write_entry(*expected)

        get_database_connection().commit()

    def cleanup():

        # NOTE: "You use a test_request_context in both setup and
        # teardown to ensure that flask.g exists."
        with app.test_request_context('/'):
            con = get_database_connection()
            cur = con.cursor()
            cur.execute("DELETE FROM entries")
            con.commit()

    # Also note that allowing the two "with" blocks to close commits the
    # transactions for each test context.

    request.addfinalizer(cleanup)

    return expected


def test_listing(with_entry):

    expected = with_entry
    actual = app.test_client().get('/').data

    for value in expected:

        assert value in actual


def test_add_entries(db):

    entry_data = {
        u'title': u'Hello',
        u'text': u'This is a post',
    }

    # "The post method of the Flask test_client sends an HTTP POST
    # request to the provided URL."
    actual = app.test_client().post(
        '/add', data=entry_data, follow_redirects=True
    ).data

    assert 'No entries here so far' not in actual

    for expected in entry_data.values():

        # "assert that the line in entry data is also in the actual data"
        assert expected in actual


def test_do_login_success(req_context):

    username, password = ('admin', 'admin')

    # In-function imports look weird and wrong.
    # Shouldn't they be for things that might be optional
    # and thus could be skipped? Such as not unit tests?
    from journal import do_login

    assert 'logged_in' not in session

    do_login(username, password)

    assert 'logged_in' in session


def test_do_login_bad_password(req_context):

    username = 'admin'
    bad_password = 'wrongpassword'

    from journal import do_login

    with pytest.raises(ValueError):

        do_login(username, bad_password)


def test_do_login_bad_username(req_context):

    bad_username = 'wronguser'
    password = 'admin'

    from journal import do_login

    with pytest.raises(ValueError):

        do_login(bad_username, password)


def login_helper(username, password):

    login_data = {
        'username': username,
        'password': password
    }

    client = app.test_client()

    return client.post(
        '/login', data=login_data, follow_redirects=True
    )


def test_start_as_anonymous(db):

    client = app.test_client()

    anon_home = client.get('/').data

    assert SUBMIT_BTN not in anon_home


def test_login_success(db):

    # Is this unencrypted password okay because it's not deployed?
    # The walkthrough DID say "never" store passwords unencrypted...
    # "Anywhere".
    username, password = ('admin', 'admin')

    response = login_helper(username, password)

    assert SUBMIT_BTN in response.data


def test_login_fails(db):

    username, password = ('admin', 'wrong')

    response = login_helper(username, password)

    assert 'Login Failed' in response.data


def test_logout(db):

    home = login_helper('admin', 'admin').data

    assert SUBMIT_BTN in home

    client = app.test_client()

    response = client.get('/logout')

    assert SUBMIT_BTN not in response.data
    assert response.status_code == 302


















