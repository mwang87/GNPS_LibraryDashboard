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
                dbc.NavItem(dbc.NavLink("GNPS - Template Dashboard - Version 0.1", href="#")),
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
            html.H5(children='GNPS Data Selection'),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("Table USI", addon_type="prepend"),
                    dbc.Input(id='usi1', placeholder="Table USI", value=""),
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
    dbc.CardHeader(html.H5("Data Exploration")),
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
            html.Div(id="plots")
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
        ], style={"marginTop": 30}),
        html.Br(),
        dbc.Row([
            dbc.Col(
                dbc.Card(MIDDLE_DASHBOARD),
            )
        ])
    ],
    fluid=True,
    className="",
)

app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@app.callback([
                Output('usi1', 'value'),
              ],
              [Input('url', 'search')])
def determine_task(search):
    
    try:
        query_dict = urllib.parse.parse_qs(search[1:])
    except:
        query_dict = {}

    usi1 = _get_url_param(query_dict, "usi1", 'mzspec:GNPS:TASK-689f06f4bc2b4799828c63eef1dc522a-query_results/msql/merged_query_results.tsv')

    return [usi1]


import sys
PAGE_SIZE = 20

@app.callback([
                Output('output', 'children')
              ],
              [
                  Input('usi1', 'value'),
            ])
def draw_output(usi1):
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
        filter_action='custom'
    )

    return [table_obj]

@app.callback([
        Output('datatable', 'data'),
        Output('datatable', 'page_count'),
        Output('query_summary', 'children')
    ],
    [
        Input('usi1', 'value'),
        Input('datatable', "page_current"),
        Input('datatable', "page_size"),
        Input('datatable', 'sort_by'),
        Input('datatable', "filter_query")
    ])
def update_table(usi1, page_current, page_size, sort_by, filter):
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

    return [results_list, page_count, "Total Results {}".format(results_count)]


@app.callback([
        Output('plots', 'children')
    ],
    [
        Input('usi1', 'value'),
        Input('datatable', "page_current"),
        Input('datatable', "page_size"),
        Input('datatable', 'sort_by'),
        Input('datatable', "filter_query")
    ])
def update_table(usi1, page_current, page_size, sort_by, filter):
    query_parameters = {}
    query_parameters["page_current"] = page_current
    query_parameters["page_size"] = page_size
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter

    try:
        result = tasks.query_histogram.delay(usi1, query_parameters)
        #results_list, results_count = result.get()
    except:
        pass
        #return [[], 0, "Query Error"]

    return [["Plots Here"]]

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
