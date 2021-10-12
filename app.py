# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_table
import plotly.express as px
import plotly.graph_objects as go 
from dash.dependencies import Input, Output, State
import os
from zipfile import ZipFile
import urllib.parse
from flask import Flask, send_from_directory

import pandas as pd
import requests
import uuid
import werkzeug
import math

import numpy as np
from tqdm import tqdm
import urllib
import json

from collections import defaultdict
import uuid

import werkzeug
from flask_caching import Cache
import tasks



server = Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = 'GNPS - Template'

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'temp/flask-cache',
    'CACHE_DEFAULT_TIMEOUT': 0,
    'CACHE_THRESHOLD': 10000
})

server = app.server

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="https://gnps-cytoscape.ucsd.edu/static/img/GNPS_logo.png", width="120px"),
            href="https://gnps.ucsd.edu"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("GNPS - Library Explorer - Version 0.1", href="#")),
            ],
        navbar=True)
    ],
    color="light",
    dark=False,
    sticky="top",
)

DATASELECTION_CARD = [
    dbc.CardHeader(html.H5("Data Selection")),
    dbc.CardBody(
        [   
            html.H5(children='Filters'),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("Peak Histogram Min intensity norm (out of 1.0)", addon_type="prepend"),
                    dbc.Input(id='intensitynormmin', placeholder="intensitynormmin", value="0.0"),
                ],
                className="mb-3",
            ),
        ]
    )
]

LEFT_DASHBOARD = [
    html.Div(
        [
            html.Div(DATASELECTION_CARD),
        ]
    )
]

MIDDLE_DASHBOARD = [
    dbc.CardHeader(html.H5("Library Exploration")),
    dbc.CardBody(
        [
            html.Div(id="query_summary"),
            html.Br(),
            dcc.Loading(
                id="output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
            html.Br(),
            html.Hr(),
            dcc.Loading(
                id="plots",
                children=[html.Div([html.Div(id="loading-output-24")])],
                type="default",
            ),
            html.Hr(),
            dcc.Loading(
                id="spectrumrendering",
                children=[html.Div([html.Div(id="loading-output-25")])],
                type="default",
            ),
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Mingxun Wang PhD - UC San Diego",
            html.Br(),
            html.Br(),
            html.H5("Citation"),
            html.A('Mingxun Wang, Jeremy J. Carver, Vanessa V. Phelan, Laura M. Sanchez, Neha Garg, Yao Peng, Don Duy Nguyen et al. "Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking." Nature biotechnology 34, no. 8 (2016): 828. PMID: 27504778', 
                    href="https://www.nature.com/articles/nbt.3597")
        ]
    )
]

EXAMPLES_DASHBOARD = [
    dbc.CardHeader(html.H5("Examples")),
    dbc.CardBody(
        [
            html.A('MassIVE-KB Candidate Spectra', 
                    href="/?usi1=mzspec:GNPS:TASK-3ba5c4280636448eb4504e3e3a2f3e25-all_library_spectrum_candidates_file/"),
        ]
    )
]

BODY = dbc.Container(
    [
        dcc.Location(id='url', refresh=False),
        dbc.Row([
            dbc.Col(
                dbc.Card(MIDDLE_DASHBOARD),
            )
        ], style={"marginTop": 30}),
        html.Br(),
        dbc.Row([
            dbc.Col(
                dbc.Card(LEFT_DASHBOARD),
                className="w-50"
            ),
            dbc.Col(
                [
                    dbc.Card(CONTRIBUTORS_DASHBOARD),
                    html.Br(),
                    dbc.Card(EXAMPLES_DASHBOARD)
                ],
                className="w-50"
            ),
        ])
    ],
    fluid=True,
    className="",
)

app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

# @app.callback([
#                 Output('usi1', 'value'),
#               ],
#               [Input('url', 'search')])
# def determine_task(search):
    
#     try:
#         query_dict = urllib.parse.parse_qs(search[1:])
#     except:
#         query_dict = {}

#     usi1 = _get_url_param(query_dict, "usi1", 'mzspec:GNPS:TASK-689f06f4bc2b4799828c63eef1dc522a-query_results/msql/merged_query_results.tsv')

#     return [usi1]


import sys
PAGE_SIZE = 20

@app.callback([
                Output('output', 'children')
              ],
              [
                  Input('url', 'search'),
            ])
def draw_output(search):
    result = tasks.task_query_data.delay({})
    results_list, results_count = result.get()

    table_obj = dash_table.DataTable(
        id='datatable',
        columns=[
            {"name": i, "id": i} for i in sorted(results_list[0])
        ],
        page_current=0,
        page_size=PAGE_SIZE,
        sort_action="custom",
        page_action='custom',
        filter_action='custom',
        row_selectable='single',
        style_cell_conditional=[
            {
                'if': {'column_id': c},
                'textAlign': 'left'
            } for c in results_list[0]
        ],
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)',
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        },
        css=[{'selector': '.row', 'rule': 'margin: 0'}],
        style_table={
            'overflowX': 'auto'
        },
        style_cell={
            'overflow': 'hidden',
            'textOverflow': 'ellipsis',
            'maxWidth': 0,
        },
        tooltip_delay=0,
        tooltip_duration=None,
        tooltip_data=[
            {
                column: {'value': str(value), 'type': 'markdown'}
                for column, value in row.items()
            } for row in results_list
        ],
    )

    return [table_obj]

@app.callback([
        Output('datatable', 'data'),
        Output('datatable', 'tooltip_data'),
        Output('datatable', 'page_count'),
        Output('query_summary', 'children')
    ],
    [
        Input('datatable', "page_current"),
        Input('datatable', "page_size"),
        Input('datatable', 'sort_by'),
        Input('datatable', "filter_query")
    ])
def update_table(page_current, page_size, sort_by, filter):
    query_parameters = {}
    query_parameters["page_current"] = page_current
    query_parameters["page_size"] = page_size
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter

    try:
        result = tasks.task_query_data.delay(query_parameters)
        results_list, results_count = result.get()
    except:
        return [[], 0, "Query Error"]

    page_count = math.ceil(results_count / page_size)

    # Adding tool tips
    tooltip_data = [
        {
            column: {'value': str(value), 'type': 'markdown'}
            for column, value in row.items()
        } for row in results_list
    ]

    return [results_list, tooltip_data, page_count, "Total Results {}".format(results_count)]


@app.callback([
        Output('plots', 'children')
    ],
    [
        Input('datatable', "page_current"),
        Input('datatable', "page_size"),
        Input('datatable', 'sort_by'),
        Input('datatable', "filter_query"),
        Input('intensitynormmin', 'value')
    ])
def update_table(page_current, page_size, sort_by, filter, intensitynormmin):
    query_parameters = {}
    query_parameters["page_current"] = page_current
    query_parameters["page_size"] = page_size
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter
    
    library_count_result = tasks.query_library_counts.delay()
    library_count_result = library_count_result.get()

    table_obj = dash_table.DataTable(
        columns=[
            {"name": i, "id": i} for i in library_count_result[0]
        ],
        page_current=0,
        page_size=PAGE_SIZE,
        data=library_count_result,
    )

    # Creating library size bar chart
    library_count_df = pd.DataFrame(library_count_result)
    library_count_df["numberspectra"] = library_count_df['EXPR$1']
    library_count_fig = px.bar(library_count_df, y='library_membership', x='numberspectra', log_x=True, orientation="h", height=800)

    # Creating histogram by m/z
    result = tasks.plot_peak_histogram.delay(query_parameters, intensitynormmin=intensitynormmin)
    result = result.get()

    histogram_df = pd.DataFrame(result)
    histogram_fig = px.bar(x=histogram_df["mz"], y=histogram_df["counts"], labels={'x': "mz", 'y':'count'})
    histogram_fig.update_layout(bargap=0)
    histogram_fig.update_traces(marker=dict(line=dict(width=0)))

    return [["Library Sizes", html.Br(), html.Br(), dcc.Graph(figure=library_count_fig), html.Br(), dcc.Graph(figure=histogram_fig)]]

@app.callback([
                Output('spectrumrendering', 'children')
              ],
              [
                  Input('datatable', 'derived_virtual_data'),
                  Input('datatable', 'derived_virtual_selected_rows'),
              ])
def draw_spectrum(table_data, table_selected):
    try:
        selected_row = table_data[table_selected[0]]
    except:
        return ["Choose Match to Show Mirror Plot"]

    selected_usi = "mzspec:GNPS:GNPS-LIBRARY:accession:" + selected_row["spectrum_id"]

    mirror_plot_params = {
        'usi1':selected_usi,
        'width': 10.0,
        'height': 6.0,
        # 'mz_min': ,
        'max_intensity': 150.0,
        'grid': 'true',
        # 'annotate_peaks': '[[114.0924,412.3234],[114.0919,171.1169,412.3233]]',
        'annotate_precision': 4,
        'annotation_rotation': 90,
    }

    url_params = urllib.parse.urlencode(mirror_plot_params)

    usi_url = "https://metabolomics-usi.ucsd.edu/svg"
    r = requests.get(usi_url, params = mirror_plot_params)

    img_obj = html.Img(src=usi_url + "?" + url_params)

    return [img_obj]

# API
@server.route("/api")
def api():
    return "Up"

@server.route("/load")
def load():
    tasks.task_library_download.delay()
    return "Loading"

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
