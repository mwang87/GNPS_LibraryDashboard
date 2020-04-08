# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import plotly.express as px
from dash.dependencies import Input, Output
import os
from zipfile import ZipFile
import urllib.parse
from flask import Flask

import pandas as pd
import requests


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=external_stylesheets)
server = app.server

#Loading Data
library_df = pd.DataFrame(requests.get("https://gnps-external.ucsd.edu/gnpslibraryjson").json()[:100])
library_df["Precursor_MZ"] = library_df["Precursor_MZ"].astype(float)

# Formatting options
library_names = list(set(library_df["library_membership"]))
dropdown_list = [{"label" : library_name, "value": library_name} for library_name in library_names]

app.layout = html.Div(
    [
        html.H1(children='GNPS Library Summary Dashboard'),
        html.Div(id='version', children="Version - Release_1"),
        dcc.Graph(figure=px.histogram(library_df, x="Precursor_MZ", color="library_membership")),
        html.H2(children='Library Selection'),
        dcc.Dropdown(
            id='library-filter',
            options=dropdown_list,
            value=["GNPS-LIBRARY"],
            multi=True
        ),
        html.Div([
            dcc.Loading(
                id="library-mz-histogram",
                children=[html.Div([html.Div(id="loading-output-2")])],
                type="default",
            )
        ]),
        html.Div([
            dcc.Loading(
                id="library-instrument-histogram",
                children=[html.Div([html.Div(id="loading-output-3")])],
                type="default",
            )
        ]),
        html.H2(children='Library Table List'),
        html.Div([
            dcc.Loading(
                id="library-table",
                children=[html.Div([html.Div(id="loading-output-4")])],
                type="default",
            )
        ])
    ]
)

# This function will rerun at any 
@app.callback(
    [Output('library-mz-histogram', 'children'), Output('library-instrument-histogram', 'children'), Output('library-table', 'children')],
    [Input('library-filter', 'value')],
)
def filter_library_histogram(search_values):

    filtered_df = library_df[library_df["library_membership"].isin(search_values)]
    fig1 = px.histogram(filtered_df, x="Precursor_MZ", color="library_membership")
    fig1.update_layout(
        autosize=True,
        height=600,
    )

    fig2 = px.histogram(filtered_df, x="Instrument")
    fig2.update_layout(
        autosize=True,
        height=600,
    )

    white_list_columns = ["spectrum_id", "library_membership", "Compound_Name", "Ion_Source", "Instrument", "create_time", "Precursor_MZ"]
    table_fig = dash_table.DataTable(
        columns=[
            {"name": i, "id": i, "deletable": True, "selectable": True} for i in white_list_columns
        ],
        data=filtered_df.to_dict('records'),
        editable=True,
        filter_action="native",
        sort_action="native",
        sort_mode="multi",
        column_selectable="single",
        row_selectable="multi",
        row_deletable=True,
        selected_columns=[],
        selected_rows=[],
        page_action="native",
        page_current= 0,
        page_size= 10,
    )

    import gc
    del filtered_df
    gc.collect()

    return [dcc.Graph(figure=fig1), dcc.Graph(figure=fig2), table_fig]

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
