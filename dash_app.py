from dash import Dash, html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import dash.dash_table as dt
import plotly.express as px
import pandas as pd

import simulation


app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server


def make_layout():
    return dbc.Container([
        dbc.Row(dbc.Col(html.H2("🏥 Hospital Triage — Dash Prototype"), width=12)),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Simulation Controls"),
                    dbc.CardBody([
                        dbc.Label("Number of Staff"),
                        dcc.Input(id='num-docs', type='number', min=1, max=20, value=3, step=1),
                        html.Br(), html.Br(),
                        dbc.Label("Avg Minutes Between Arrivals"),
                        dcc.Input(id='avg-arrival', type='number', min=0.1, value=10, step=0.1),
                        html.Br(), html.Br(),
                        dbc.Label("Simulation Run Time (mins)"),
                        dcc.Input(id='sim-time', type='number', min=10, value=480, step=10),
                        html.Br(), html.Br(),
                        dbc.Button("Run Simulation", id='run-btn', color='primary', n_clicks=0),
                        html.Div(id='run-status', style={'marginTop': '10px'})
                    ])
                ])
            ], width=3),

            dbc.Col([
                dbc.Row(dbc.Col(dcc.Graph(id='box-fig'))),
                dbc.Row(dbc.Col(dcc.Graph(id='pie-fig'))),
            ], width=9)
        ], className='mt-3'),

        dbc.Row(dbc.Col(html.H4("Detailed Logs"), width=12)),
        dbc.Row(dbc.Col(dt.DataTable(id='log-table', page_size=10), width=12)),

        dcc.Store(id='df-store')
    ], fluid=True)


app.layout = make_layout()


@app.callback(
    Output('df-store', 'data'),
    Output('run-status', 'children'),
    Input('run-btn', 'n_clicks'),
    State('num-docs', 'value'),
    State('avg-arrival', 'value'),
    State('sim-time', 'value'),
)
def run_sim(n_clicks, num_docs, avg_arrival, sim_time):
    if not n_clicks:
        return dash_no_update, "Ready"

    try:
        df = simulation.run_simulation(int(num_docs), float(avg_arrival), float(sim_time), seed=None)
        if df is None or df.empty:
            return {}, "No data generated (try longer run time)."
        return df.to_json(date_format='iso', orient='split'), f"Finished — {len(df)} patients"
    except Exception as e:
        return {}, f"Error: {e}"


@app.callback(
    Output('box-fig', 'figure'),
    Output('pie-fig', 'figure'),
    Output('log-table', 'data'),
    Output('log-table', 'columns'),
    Input('df-store', 'data')
)
def update_outputs(df_json):
    if not df_json:
        # Empty placeholders
        return {}, {}, [], []

    df = pd.read_json(df_json, orient='split')

    fig_box = px.box(df, x='Severity', y='Wait Time (min)', color='Severity',
                     color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})

    throughput_df = df.groupby('Severity').count().reset_index()
    fig_pie = px.pie(throughput_df, values='ID', names='Severity', hole=0.4,
                     color='Severity', color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})

    data = df.to_dict('records')
    columns = [{'name': c, 'id': c} for c in df.columns]
    return fig_box, fig_pie, data, columns


if __name__ == '__main__':
    app.run(debug=True, port=8050)
