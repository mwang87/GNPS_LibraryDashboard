# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
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
library_df = pd.DataFrame(requests.get("https://gnps-external.ucsd.edu/gnpslibraryjson").json())
library_df["Precursor_MZ"] = library_df["Precursor_MZ"].astype(float)

# Formatting options
library_names = list(set(library_df["library_membership"]))
dropdown_list = [{"label" : library_name, "value": library_name} for library_name in library_names]

app.layout = html.Div(
    [
        html.H1(children='GNPS Library Dashboard'),
        html.Div(id='version', children="Version - Release_1"),
        dcc.Dropdown(
            id='library-filter',
            options=dropdown_list,
            value=library_names,
            multi=True
        ),
        html.Div([
            dcc.Loading(
                id="library-filter-histogram",
                children=[html.Div([html.Div(id="loading-output-2")])],
                type="default",
            )
        ])
    ]
)

# This function will rerun at any 
@app.callback(
    Output('library-filter-histogram', 'children'),
    [Input('library-filter', 'value')],
)
def filter_library_histogram(search_values):
    filtered_df = library_df[library_df["library_membership"].isin(search_values)]
    fig = px.histogram(filtered_df, x="Precursor_MZ", color="library_membership")
    fig.update_layout(
        autosize=True,
        height=600,
    )
    return dcc.Graph(figure=fig)

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
