import contextlib # closing

import pytest

import journal # app, connect_db, get_database_connection, init_db


TEST_DSN = 'dbname=test_learning_journal user=fried'


# Used for testing isolation. The wipe half of reinitting the database.
def clear_db():

    # This ensures the connection is closed later.
    # Context library is all for this kind of context stuff.
    with contextlib.closing(journal.connect_db()) as db:

        # Testing is not supposed to be used with a deployed database,
        # apparently. That's where TEST_DSN's specification comes in:
        # This will all be done in the test_learning_journal db.
        # ...
        # NOTE!! This database must be created manually on the CLI!
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
    journal.app.config['DATABASE'] = TEST_DSN
    journal.app.config['TESTING'] = True


# "The fixture function is defined with parameters.
# The names of the parameters must match registered fixtures.
# The fixtures named as parameters will be run surrounding the new fixture."
@pytest.fixture(scope='session')
def db(test_app, request):

    ''' Initialize the entries table and drop it when finished. '''

    # This is the "fixture function" with its "registered fixture" parameters.
    # The request parameter is a fixture that pytest gives you; you use it
    # to connect the cleanuo() function to the db fixture.

    journal.init_db()

    # Unexplained methods: cleardb addfinalizer cleanup

    # This here is a closure?
    # Or is it just using some dark magic from the pytest decorator?
    # ...
    # "The request parameter is a fixture that pytest registers.
    # You use it to connect the cleanup function to the db fixture.
    # This means that cleanup will be run after tests are complete
    # as a tear-down action."
    # I really wish this was namespaced so this stuff was clearer.
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

    ''' Run tests within a test request context so that 'g' is present.  '''

    # Wait... flask.g would not be available if we didn't make this
    # "request context" function??

    with journal.app.test_request_context('/'):

        # First, yield nothing.
        # Wat.
        yield

        con = journal.get_database_connection()
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

    con = journal.get_database_connection()
    cur = con.cursor()

    cur.execute(query, params)

    return cur.fetchall()


def test_write_entry(req_context):

    from journal import write_entry

    expected = ("My Title", "My Text")

    # Remember, star args are just how you unpack things.
    # ((double star args unpack things inot a dict.))
    write_entry(*expected)

    # "run_independent_query() is a 'helper function' you can re-use."
    # Where's it come from, pytest? By way of the decorator??
    rows = run_independent_query("SELECT * FROM entries")


    # Huh, so this is just assertEquals... from pytest?
    # Maybe notm since it's its own freestanding operation?
    assert len(rows) == 1

    for val in expected:

        assert val in rows[0]


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
    actual = journal.app.test_client().get('/').data
    expected = 'No entries here so far'
    assert expected in actual


@pytest.fixture(scope='function')
def with_entry(db, request):

    from journal import write_entry

    expected = (u'Test Title)', u'Test Text')

    with journal.app.test_request_context('/'):

        journal.write_entry(*expected)

        journal.get_database_connection().commit()

    def cleanup():

        # Is THIS a callback function? Hrm, a hole in my knowledge!
        # I'll mend it when I'm less sleepy.

        # NOTE: "You use a test_request_context in both setup and
        # teardown to ensure that flask.g exists."
        with journal.app.test_request_context('/'):
            con = journal.get_database_connection()
            cur = con.cursor()
            cur.execute("DELETE FROM entries")
            con.commit()

    # Also note that allowing the two "with" blocks to close commits the
    # transactions for each test context.

    request.addfinalizer(cleanup)

    return expected


def test_listing(with_entry):

    expected = with_entry
    actual = journal.app.test_client().get('/').data

    for value in expected:

        assert value in actual















