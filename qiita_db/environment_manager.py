# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------
from os.path import abspath, dirname, join
from functools import partial
from os import mkdir
from os.path import exists
import gzip

from future import standard_library
from future.utils import viewitems
with standard_library.hooks():
    from urllib.request import urlretrieve

from qiita_core.exceptions import QiitaEnvironmentError
from qiita_core.qiita_settings import qiita_config
from .sql_connection import SQLConnectionHandler
from .reference import Reference

get_support_file = partial(join, join(dirname(abspath(__file__)),
                                      'support_files'))
reference_base_dir = join(qiita_config.base_data_dir, "reference")
get_reference_fp = partial(join, reference_base_dir)


DFLT_BASE_WORK_FOLDER = get_support_file('work_data')
SETTINGS_FP = get_support_file('qiita-db-settings.sql')
LAYOUT_FP = get_support_file('qiita-db.sql')
INITIALIZE_FP = get_support_file('initialize.sql')
POPULATE_FP = get_support_file('populate_test_db.sql')
ENVIRONMENTS = {'demo': 'qiita_demo', 'test': 'qiita_test',
                'production': 'qiita'}
CLUSTERS = ['demo', 'reserved', 'general']


def _check_db_exists(db, conn_handler):
    r"""Checks if the database db exists on the postgres server

    Parameters
    ----------
    db : str
        The database
    conn_handler : SQLConnectionHandler
        The connection to the database
    """
    dbs = conn_handler.execute_fetchall('SELECT datname FROM pg_database')

    # It's a list of tuples, so just create the tuple to check if exists
    return (db,) in dbs


def _create_layout_and_init_db(conn):
    print('Building SQL layout')
    # Create the schema
    with open(LAYOUT_FP, 'U') as f:
        conn.execute(f.read())

    print('Initializing database')
    # Initialize the database
    with open(INITIALIZE_FP, 'U') as f:
        conn.execute(f.read())


def _populate_test_db(conn):
    print('Populating database with demo data')
    with open(POPULATE_FP, 'U') as f:
        conn.execute(f.read())


def _add_ontology_data(conn):
    print ('Loading Ontology Data')
    if not exists(reference_base_dir):
        mkdir(reference_base_dir)

    fp = get_reference_fp('ontologies.sql.gz')

    if exists(fp):
        print("SKIPPING download of ontologies: File already exists at %s. "
              "To download the file again, delete the existing file first."
              % fp)
    else:
        url = 'ftp://thebeast.colorado.edu/pub/qiita/qiita_ontoandvocab.sql.gz'
        try:
            urlretrieve(url, fp)
        except:
            raise IOError("Error: Could not fetch ontologies file from %s" %
                          url)

    with gzip.open(fp, 'rb') as f:
        conn.execute(f.read())


def _insert_processed_params(conn, ref):
    sortmerna_sql = """INSERT INTO qiita.processed_params_sortmerna
                       (reference_id, evalue, max_pos, similarity, coverage,
                        threads)
                       VALUES
                       (%s, 1, 10000, 0.97, 0.97, 1)"""

    conn.execute(sortmerna_sql, [ref._id])


def _download_reference_files(conn):
    print('Downloading reference files')
    if not exists(reference_base_dir):
        mkdir(reference_base_dir)

    files = {'tree': (get_reference_fp('gg_13_8-97_otus.tree'),
                      'ftp://thebeast.colorado.edu/greengenes_release/'
                      'gg_13_8_otus/trees/97_otus.tree'),
             'taxonomy': (get_reference_fp('gg_13_8-97_otu_taxonomy.txt'),
                          'ftp://thebeast.colorado.edu/greengenes_release/'
                          'gg_13_8_otus/taxonomy/97_otu_taxonomy.txt'),
             'sequence': (get_reference_fp('gg_13_8-97_otus.fasta'),
                          'ftp://thebeast.colorado.edu/greengenes_release/'
                          'gg_13_8_otus/rep_set/97_otus.fasta')}

    for file_type, (local_fp, url) in viewitems(files):
        # Do not download the file if it exists already
        if exists(local_fp):
            print("SKIPPING %s: file already exists at %s. To "
                  "download the file again, erase the existing file first" %
                  (file_type, local_fp))
        else:
            try:
                urlretrieve(url, local_fp)
            except:
                raise IOError("Error: Could not fetch %s file from %s" %
                              (file_type, url))

    ref = Reference.create('Greengenes', '13_8', files['sequence'][0],
                           files['taxonomy'][0], files['tree'][0])

    _insert_processed_params(conn, ref)


def make_environment(load_ontologies, download_reference, add_demo_user):
    r"""Creates the new environment specified in the configuration

    Parameters
    ----------
    load_ontologies : bool
        Whether or not to retrieve and unpack ontology information
    download_reference : bool
        Whether or not to download greengenes reference files
    add_demo_user : bool
        Whether or not to add a demo user to the database with username
        demo@microbio.me and password "password"

    Raises
    ------
    IOError
        If `download_reference` is true but one of the files cannot be
        retrieved
    QiitaEnvironmentError
        If the environment already exists
    """
    # Connect to the postgres server
    admin_conn = SQLConnectionHandler(admin=True)

    # Check that it does not already exists
    if _check_db_exists(qiita_config.database, admin_conn):
        raise QiitaEnvironmentError(
            "Database {0} already present on the system. You can drop it "
            "by running 'qiita_env drop'".format(qiita_config.database))

    # Create the database
    print('Creating database')
    admin_conn.execute('CREATE DATABASE %s' % qiita_config.database)

    del admin_conn

    # Connect to the postgres server, but this time to the just created db
    conn = SQLConnectionHandler()

    print('Inserting database metadata')
    # Build the SQL layout into the database
    with open(SETTINGS_FP, 'U') as f:
        conn.execute(f.read())

    # Insert the settings values to the database
    conn.execute("INSERT INTO settings (test, base_data_dir, base_work_dir) "
                 "VALUES (%s, %s, %s)",
                 (qiita_config.test_environment, qiita_config.base_data_dir,
                  qiita_config.working_dir))

    _create_layout_and_init_db(conn)

    if load_ontologies:
        _add_ontology_data(conn)

    if download_reference:
        _download_reference_files(conn)

    # we don't do this if it's a test environment because populate.sql
    # already adds this user...
    if add_demo_user and not qiita_config.test_environment:
        conn.execute("""
            INSERT INTO qiita.qiita_user (email, user_level_id, password,
                                          name, affiliation, address, phone)
            VALUES
            ('demo@microbio.me', 4,
             '$2a$12$gnUi8Qg.0tvW243v889BhOBhWLIHyIJjjgaG6dxuRJkUM8nXG9Efe',
             'Demo', 'Qitta Dev', '1345 Colorado Avenue', '303-492-1984')""")

        print('Demo user successfully created')

    if qiita_config.test_environment:
        _populate_test_db(conn)
        print('Test environment successfully created')
    else:
        print('Production environment successfully created')


def drop_environment(ask_for_confirmation):
    """Drops the database specified in the configuration
    """
    # Connect to the postgres server
    conn = SQLConnectionHandler()
    settings_sql = "SELECT test FROM settings"
    is_test_environment = conn.execute_fetchone(settings_sql)[0]

    del conn

    if is_test_environment:
        do_drop = True
    else:
        if ask_for_confirmation:
            confirm = ''
            while confirm not in ('Y', 'y', 'N', 'n'):
                confirm = raw_input("THIS IS NOT A TEST ENVIRONMENT.\n"
                                    "Proceed with drop? (y/n)")

            do_drop = confirm in ('Y', 'y')
        else:
            do_drop = True

    if do_drop:
        admin_conn = SQLConnectionHandler(admin=True)
        admin_conn.execute('DROP DATABASE %s' % qiita_config.database)
    else:
        print('ABORTING')


def reset_test_database(wrapped_fn):
    """Decorator that drops the qiita schema, rebuilds and repopulates the
    schema with test data, then executes wrapped_fn
    """
    conn_handler = SQLConnectionHandler()

    def decorated_wrapped_fn(*args, **kwargs):
        # Drop the schema
        try:
            conn_handler.execute("DROP SCHEMA qiita CASCADE")
        except:
            # ignore the failure of the drop if the schema already doesnt exist
            # generic Error raised so can't catch specific error
            pass
        # Create the schema
        with open(LAYOUT_FP, 'U') as f:
            conn_handler.execute(f.read())
        # Initialize the database
        with open(INITIALIZE_FP, 'U') as f:
            conn_handler.execute(f.read())
        # Populate the database
        with open(POPULATE_FP, 'U') as f:
            conn_handler.execute(f.read())
        # Execute the wrapped function
        return wrapped_fn(*args, **kwargs)

    return decorated_wrapped_fn


def clean_test_environment():
    r"""Cleans the test database environment.

    In case that the test database is dirty (i.e. the 'qiita' schema is
    present), this cleans it up by dropping the 'qiita' schema and
    re-populating it.
    """
    # First, we check that we are not in a production environment
    conn_handler = SQLConnectionHandler()
    # It is possible that we are connecting to a production database
    test_db = conn_handler.execute_fetchone("SELECT test FROM settings")[0]
    # Or the loaded configuration file belongs to a production environment
    # or the test database is not qiita_test
    if not qiita_config.test_environment or not test_db \
            or qiita_config.database != 'qiita_test':
        raise RuntimeError("Working in a production environment. Not "
                           "executing the test cleanup to keep the production "
                           "database safe.")

    # wrap the dummy function and execute it
    @reset_test_database
    def dummyfunc():
        pass
    dummyfunc()
