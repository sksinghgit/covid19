import logging
import plotly.graph_objects as go
import dash
import dash_table
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from worldometer_scrapper import CovidData


logger = logging.getLogger('covid19')
GRAPH_UPDATE_INTERVAL = 20*60*1000 # 20 mins
MAX_COUNTRIES = 30
PIXEL_FOR_CHAR=5
out_file = 'covid19.json'
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
covid_data = CovidData()


class Plotter(object):

    def __init__(self, data_file):
        self.data_file = data_file
        self.fig_confirmed = go.Figure()
        self.fig_deaths = go.Figure()
        self.fig_recovered = go.Figure()
        self.fig_active = go.Figure()
        self.fig_new_cases = go.Figure()
        self.fig_new_deaths = go.Figure()
        self.fig_new_recovered = go.Figure()
        self.checksum = ''
        self.all_countries = []
        self.data = {}
        self.load_data()

    def __get_data_checksum(self, data):
        return hash(repr(data))

    def __reload_required(self, data):
        checksum = self.__get_data_checksum(data)
        logger.info("old checksum: {} new checksum: {}".format(self.checksum, checksum))
        ret_val = self.checksum != checksum
        self.checksum = checksum
        return ret_val

    def __get_top_countries(self, data):
        items = sorted(data.items(), key = lambda kv:kv[1][-1]['Total Cases'], reverse=True)
        country_list = [item[0] for item in items]
        return country_list[0:MAX_COUNTRIES]

    def load_data(self):
        logger.info("Plotter.load_data called")
        self.data = covid_data.get_historical_data()
        if not self.__reload_required(self.data):
            return

        self.all_countries = list(self.data.keys())
        countries = self.__get_top_countries(self.data)
        self.fig_confirmed = go.Figure()
        self.fig_deaths = go.Figure()
        self.fig_recovered = go.Figure()
        self.fig_active = go.Figure()
        self.fig_new_cases = go.Figure()
        self.fig_new_deaths = go.Figure()
        self.fig_new_recovered = go.Figure()
        for country in countries:
            if country.casefold() == "china":
                continue
            date = []
            confirmed_list = []
            deaths_list = []
            recovered_list = []
            new_cases = []
            new_deaths = []
            new_recovered = []
            active_list = []
            prev_recovered = 0
            for entry in self.data[country]:
                date.append(entry['date'])
                recovered = entry['Total Cases'] - entry['Active Cases'] - entry['Total Deaths']
                confirmed_list.append(entry['Total Cases'])
                deaths_list.append(entry['Total Deaths'])
                recovered_list.append(recovered)
                active_list.append(entry['Active Cases'])
                new_cases.append(entry['New Cases'])
                new_deaths.append(entry['New Deaths'])
                new_recovered.append(recovered - prev_recovered)
                prev_recovered = recovered
            self.fig_confirmed.add_trace(go.Scatter(x=date, y=confirmed_list, mode='lines+markers', name=country))
            self.fig_deaths.add_trace(go.Scatter(x=date, y=deaths_list, mode='lines+markers', name=country))
            self.fig_recovered.add_trace(go.Scatter(x=date, y=recovered_list, mode='lines+markers', name=country))
            self.fig_active.add_trace(go.Scatter(x=date, y=active_list, mode='lines+markers', name=country))
            self.fig_new_cases.add_trace(go.Scatter(x=date, y=new_cases, mode='lines+markers', name=country))
            self.fig_new_deaths.add_trace(go.Scatter(x=date, y=new_deaths, mode='lines+markers', name=country))
            self.fig_new_recovered.add_trace(go.Scatter(x=date, y=new_recovered, mode='lines+markers', name=country))

    def get_country_graph(self, country):
        fig_country = go.Figure()
        if country in self.data:
            country_data = self.data[country]
            date = []
            confirmed_list = []
            deaths_list = []
            recovered_list = []
            new_cases = []
            new_deaths = []
            new_recovered = []
            active_list = []
            prev_recovered = 0
            for entry in country_data:
                date.append(entry['date'])
                deaths = entry.get('Total Deaths', 0)
                recovered = entry['Total Cases'] - entry['Active Cases'] - deaths
                confirmed_list.append(entry['Total Cases'])
                deaths_list.append(deaths)
                recovered_list.append(recovered)
                active_list.append(entry['Active Cases'])
                new_cases.append(entry['New Cases'])
                new_deaths.append(entry.get('New Deaths', 0))
                new_recovered.append(recovered - prev_recovered)
                prev_recovered = recovered
            fig_country.add_trace(go.Scatter(x=date, y=confirmed_list, mode='lines+markers', name='Total Cases'))
            fig_country.add_trace(go.Scatter(x=date, y=new_cases, mode='lines+markers', name='New Cases'))
            fig_country.add_trace(go.Scatter(x=date, y=deaths_list, mode='lines+markers', name='Total Deaths'))
            fig_country.add_trace(go.Scatter(x=date, y=new_deaths, mode='lines+markers', name='New Deaths'))
            fig_country.add_trace(go.Scatter(x=date, y=active_list, mode='lines+markers', name='Active Cases'))
            fig_country.add_trace(go.Scatter(x=date, y=recovered_list, mode='lines+markers', name='Recovered'))
            fig_country.add_trace(go.Scatter(x=date, y=new_recovered, mode='lines+markers', name='New Recovered'))
        return fig_country


plotter = Plotter(out_file)

@app.callback(Output('reload-data', 'children'),
              [Input('interval-component', 'n_intervals')])
def update_metrics(n):
    plotter.load_data()
    return ""


def get_live_stats_columns():
    column_ids, column_names = covid_data.get_live_columns()
    columns = []
    for i in  range(len(column_ids)):
        columns.append({'name': column_names[i], 'id' : column_ids[i]})
    return columns


def get_live_stats_data():
    table = covid_data.get_todays_stats()
    return table.to_dict('rows')


@app.callback(Output('stats_table', 'data'),
              [Input('interval-component', 'n_intervals')])
def update_live_stats(n):
    return get_live_stats_data()

@app.callback(Output('confirmed', 'children'),
              [Input('country_dropdown', 'value')])
def update_confirmed_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("Confirmed Cases"),
            dcc.Graph(id='confirmed_graph',
                      figure=plotter.fig_confirmed)
        ], className="twelve columns")

    return ""

@app.callback(Output('new_cases', 'children'),
              [Input('country_dropdown', 'value')])
def update_new_cases_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("New Cases"),
            dcc.Graph(id='new_cases_graph',
                      figure=plotter.fig_new_cases)
        ], className="twelve columns")

    return ""

@app.callback(Output('deaths', 'children'),
              [Input('country_dropdown', 'value')])
def update_deaths_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("Total Deaths"),
            dcc.Graph(id='deaths_graph',
                      figure=plotter.fig_deaths)
        ], className="twelve columns")

    return ""

@app.callback(Output('new_deaths', 'children'),
              [Input('country_dropdown', 'value')])
def update_new_deaths_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("New Deaths"),
            dcc.Graph(id='new_deaths_graph',
                      figure=plotter.fig_new_deaths)
        ], className="twelve columns")

    return ""

@app.callback(Output('active', 'children'),
              [Input('country_dropdown', 'value')])
def update_active_graph_live(value):
    if value == 'All':
        return html.Div([
            html.H3("Active Cases"),
            dcc.Graph(id='active_graph',
                      figure=plotter.fig_active)
        ], className="twelve columns")

    return ""

@app.callback(Output('recovered', 'children'),
              [Input('country_dropdown', 'value')])
def update_recovered_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("Total Recovered"),
            dcc.Graph(id='recovered_graph',
                      figure=plotter.fig_recovered)
        ], className="twelve columns")

    return ""

@app.callback(Output('new_recovered', 'children'),
              [Input('country_dropdown', 'value')])
def update_new_recovered_graph_dropdown(value):
    if value == 'All':
        return html.Div([
            html.H3("New Recovered"),
            dcc.Graph(id='new_recovered_graph',
                      figure=plotter.fig_new_recovered)
        ], className="twelve columns")

    return ""


def create_conditional_style():
    column_ids, column_names = covid_data.get_live_columns()
    style=[]
    for i in range(len(column_ids)):
        name_length = len(column_names[i])
        pixel = 50 + round(name_length*PIXEL_FOR_CHAR)
        pixel = str(pixel) + "px"
        style.append({'if': {'column_id': column_ids[i]}, 'minWidth': pixel})
    return style


def get_country_dropdown_options():
    options = [{'label': 'All', 'value': 'All'}]
    for country in plotter.all_countries:
        options.append({'label': country, 'value': country})
    return options


@app.callback(Output('country_graph', 'children'), [Input('country_dropdown', 'value')])
def display_graphs(value):
    if value is not None and value != '' and value != 'All':
        text = "{} COVID-19 Data".format(value)
        return html.Div([
            html.H3(text),
            dcc.Graph(id=value + '_country_graph',
                      figure=plotter.get_country_graph(value))
        ], className="twelve columns")

    return ""


app.layout = html.Div([
    html.Div([
        html.Div(id='reload-data'),
        html.Div(children=[
            html.H3('Live Stats'),
            dash_table.DataTable(id='stats_table',
                                 columns=get_live_stats_columns(),
                                 data=get_live_stats_data(),
                                 style_cell_conditional=create_conditional_style(),
                                 fixed_rows={'headers': True, 'data': 0},
                                 fixed_columns={'headers': True, 'data': 1},
                                 style_table={'maxWidth' : '1500px'})
        ]),

        html.Div(children=[
            html.H1("Select Country"),
            dcc.Dropdown(
                id='country_dropdown',
                options=get_country_dropdown_options(),
            ),

            html.Div(id='country_graph')
        ]),

        html.Div(id='confirmed'),
        html.Div(id='new_cases'),
        html.Div(id='deaths'),
        html.Div(id='new_deaths'),
        html.Div(id='active'),
        html.Div(id='recovered'),
        html.Div(id='new_recovered'),

        dcc.Interval(
            id='interval-component',
            interval=GRAPH_UPDATE_INTERVAL,
            n_intervals=0
        )
    ], className="row",)
])


def main():
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('app.log')
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    app.run_server(debug=False, host='0.0.0.0')


if __name__ == "__main__":
    main()