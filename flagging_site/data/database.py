"""This file handles all database stuff, i.e. writing and retrieving data to
the Postgres database. Note that of the functionality in this file is available
directly in the command line.

While the app is running, the database connection is managed by SQLAlchemy. The
`db` object defined near the top of the file is that connector, and is used
throughout both this file and other files in the code base. The `db` object is
connected to the actual database in the `create_app` function: the app instance
is passed in via `db.init_app(app)`, and the `db` object looks for the config
variable `SQLALCHEMY_DATABASE_URI`.
"""
import os
import pandas as pd
from typing import Optional
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy import declarative_base
from sqlalchemy.exc import ResourceClosedError
from psycopg2 import connect
from dataclasses import dataclass

db = SQLAlchemy()
Base = declarative_base()


def execute_sql(query: str) -> Optional[pd.DataFrame]:
    """Execute arbitrary SQL in the database. This works for both read and
    write operations. If it is a write operation, it will return None;
    otherwise it returns a Pandas dataframe.

    Args:
        query: (str) A string that contains the contents of a SQL query.

    Returns:
        Either a Pandas Dataframe the selected data for read queries, or None
        for write queries.
    """
    with db.engine.connect() as conn:
        res = conn.execute(query)
        try:
            df = pd.DataFrame(
                res.fetchall(),
                columns=res.keys()
            )
            return df
        except ResourceClosedError:
            return None


def execute_sql_from_file(file_name: str) -> Optional[pd.DataFrame]:
    """Execute SQL from a file in the `QUERIES_DIR` directory, which should be
    located at `flagging_site/data/queries`.

    Args:
        file_name: (str) A file name inside the `QUERIES_DIR` directory. It
                   should be only the file name alone and not the full path.

    Returns:
        Either a Pandas Dataframe the selected data for read queries, or None
        for write queries.
    """
    path = os.path.join(current_app.config['QUERIES_DIR'], file_name)
    with current_app.open_resource(path) as f:
        return execute_sql(f.read().decode('utf8'))


def create_db() -> bool:
    """If the database defined by `POSTGRES_DBNAME` doesn't exist, create it
    and return True, otherwise do nothing and return False. By default, the
    config variable `POSTGRES_DBNAME` is set to "flagging".

    Returns:
        bool for whether the database needed to be created.
    """

    # connect to postgres database, get cursor
    conn = connect(
        user=current_app.config['POSTGRES_USER'],
        password=current_app.config['POSTGRES_PASSWORD'],
        host=current_app.config['POSTGRES_HOST'],
        port=current_app.config['POSTGRES_PORT'],
        dbname='postgres'
    )
    cursor = conn.cursor()

    # get a list of all databases:
    cursor.execute('SELECT datname FROM pg_database;')

    # create a list of all available database names:
    db_list = cursor.fetchall()
    db_list = [d[0] for d in db_list]

    # if that database is already there, exit out of this function
    if current_app.config['POSTGRES_DBNAME'] in db_list:
        return False
    # if the database isn't already there, proceed ...

    # create the database
    cursor.execute('COMMIT;')
    cursor.execute('CREATE DATABASE ' + current_app.config['POSTGRES_DBNAME'])
    cursor.execute('COMMIT;')

    return True


def init_db():
    """This data clears and then populates the database from scratch. You only
    need to run this function once per instance of the database.
    """
    with current_app.app_context():
        # This file drops the tables if they already exist, and then defines
        # the tables. This is the only query that CREATES tables.
        execute_sql_from_file('schema.sql')

        # The boathouses table is populated. This table doesn't change, so it
        # only needs to be populated once.
        execute_sql_from_file('define_boathouse.sql')

        # The function that updates the database periodically is run for the
        # first time.
        update_database()

        # The models available in Base are given corresponding tables if they
        # do not already exist.
        Base.metadata.create_all(db.engine)


def update_database():
    """This function basically controls all of our data refreshes. The
    following tables are updated in order:

    - usgs
    - hobolink
    - processed_data
    - model_outputs

    The functions run to calculate the data are imported from other files
    within the data folder.
    """
    options = {
        'con': db.engine,
        'index': False,
        'if_exists': 'replace'
    }

    # Populate the `usgs` table.
    from .usgs import get_live_usgs_data
    df_usgs = get_live_usgs_data()
    df_usgs.to_sql('usgs', **options)

    # Populate the `hobolink` table.
    from .hobolink import get_live_hobolink_data
    df_hobolink = get_live_hobolink_data()
    df_hobolink.to_sql('hobolink', **options)

    # Populate the `processed_data` table.
    from .predictive_models import process_data
    df = process_data(df_hobolink=df_hobolink, df_usgs=df_usgs)
    df.to_sql('processed_data', **options)

    # Populate the `model_outputs` table.
    from .predictive_models import all_models
    model_outs = all_models(df)
    model_outs.to_sql('model_outputs', **options)

    return True


@dataclass
class Boathouses(db.Model):
    reach: int = db.Column(db.Integer, unique=False)
    boathouse: str = db.Column(db.String(255), primary_key=True)
    latitude: float = db.Column(db.Numeric, unique=False)
    longitude: float = db.Column(db.Numeric, unique=False)


def get_boathouse_metadata_dict():
    """
    Return a dictionary of boathouses' metadata
    """
    boathouse_query = (Boathouses.query.all())
    return {'boathouses': boathouse_query}


def get_latest_time():
    """
    Returns the latest time in the processed data
    """
    return execute_sql('SELECT MAX(time) FROM processed_data;').iloc[0]['max']
