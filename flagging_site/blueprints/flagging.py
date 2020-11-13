import pandas as pd

from flask import Blueprint
from flask import render_template
from flask import request
from flask import current_app
from flask import flash

from ..data.manual_overrides import get_currently_overridden_boathouses
from ..data.predictive_models import latest_model_outputs
# from ..data.database import get_boathouse_by_reach_dict
from ..data.database import get_boathouse_metadata_dict
from ..data.database import get_latest_time

bp = Blueprint('flagging', __name__)


@bp.before_request
def before_request():
    # Get the latest time shown in the database
    ltime = get_latest_time()

    # Get current time from the computer clock
    ttime = pd.Timestamp.now()

    # Calculate difference between now and d.b. time
    diff = ttime - ltime

    # If more than 48 hours, flash message.
    if diff >= pd.Timedelta(48, 'hr'):
        flash('<b>Note:</b> The database has not updated in at least 48 '
              'hours. The information displayed on this page may be outdated.')

    # ~~~

    if not current_app.config['BOATING_SEASON']:
        msg = '<b>Note:</b> It is currently not boating season. '
        if request.path.startswith('/flags'):
            # If the path is the iframe...
            msg += (
                'We do not display flags when it is not boating season. We '
                'hope to see you again this spring!'
            )
        else:
            msg += (
                'We may update our database and (consequently) our predictive '
                'model while it is not boating season, but these model outputs '
                'are not intended to be used to make decisions regarding '
                'recreational activities along the Charles River.'
            )
        flash(msg)


def stylize_model_output(df: pd.DataFrame) -> str:
    """
    This function function stylizes the dataframe that we will output for our
    web page. This function replaces the bools with colorized values, and then
    returns the HTML of the table excluding the index.

    Args:
        df: (pd.DataFrame) Pandas Dataframe containing model outputs.

    Returns:
        HTML table.
    """
    df = df.copy()

    def _apply_flag(x: bool) -> str:
        flag_class = 'blue-flag' if x else 'red-flag'
        return f'<span class="{flag_class}">{x}</span>'

    df['safe'] = df['safe'].apply(_apply_flag)
    df.columns = [i.title().replace('_', ' ') for i in df.columns]

    # remove reach number
    df = df.drop(columns=['Reach'])

    return df.to_html(index=False, escape=False)


def parse_model_outputs(model_output_df: pd.DataFrame) -> dict:
    model_output_df = model_output_df.set_index('reach')

    boathouses = get_boathouse_metadata_dict()['boathouses']
    flags = {}

    # loop through all boathouses
    for boathouse in boathouses:
        flags[boathouse.boathouse] = model_output_df['safe'][boathouse.reach]

    # then set any and all overriden boathouses to False (Irregardless of model output)
    overridden_boathouses = get_currently_overridden_boathouses()

    for or_boathouse in overridden_boathouses:
        print(or_boathouse)
        flags[or_boathouse] = False

    return flags


@bp.route('/')
def index() -> str:
    """
    The home page of the website. This page contains a brief description of the
    purpose of the website, and the latest outputs for the flagging model.
    """
    df = latest_model_outputs()
    homepage = parse_model_outputs(df)
    model_last_updated_time = df['time'].iloc[0]
    boating_season = current_app.config['BOATING_SEASON']

    return render_template('index.html',
                           homepage=homepage,
                           model_last_updated_time=model_last_updated_time,
                           boating_season=boating_season)


@bp.route('/about')
def about() -> str:
    return render_template('about.html')


@bp.route('/output_model', methods=['GET'])
def output_model() -> str:
    """
    Retrieves data from hobolink and usgs, processes that data, and then
    displays the data as a human-readable, stylized HTML table.

    Returns:
        Rendering of the model outputs via the `output_model.html` template.
    """

    # Parse contents of the query string to get reach and hours parameters.
    # Defaults are hours = 24, and reach = -1.
    # When reach = -1, we utilize all reaches.
    reach = request.args.get('reach', -1, type=int)
    hours = request.args.get('hours', 24, type=int)

    # Look at no more than x_MAX_HOURS
    hours = min(max(hours, 1), current_app.config['API_MAX_HOURS'])

    df = latest_model_outputs(hours)

    # reach_html_tables is a dict where the index is the reach number
    # and the values are HTML code for the table of data to display for
    # that particular reach
    reach_html_tables = {}

    # loop through each reach in df
    #    compare with reach to determine whether to display that reach
    #       extract the subset from the df for that reach
    #       then convert that df subset to HTML code
    #       and then add that HTML subset to reach_html_tables
    for i in df['reach'].unique():
        if (reach == -1 or reach == i):
            reach_html_tables[i] = stylize_model_output(df.loc[df['reach'] == i])

    return render_template('output_model.html', tables=reach_html_tables)


@bp.route('/flags')
def flags() -> str:
    # TODO: Update to use combination of Boathouses and the predictive model
    #  outputs
    df = latest_model_outputs()
    boathouse_statuses = parse_model_outputs(df)
    model_last_updated_time = df['time'].iloc[0]
    boating_season = current_app.config['BOATING_SEASON']

    return render_template('flags.html',
                           boathouse_statuses=boathouse_statuses,
                           model_last_updated_time=model_last_updated_time,
                           boating_season=boating_season)


@bp.route('/api')
def api_index() -> str:
    """Landing page for the API."""
    return render_template('api/index.html')
