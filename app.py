# -*- coding: utf-8 -*-
import xarray as xr
import sys
import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit import Chem

import base64
import os
from io import BytesIO
from zipfile import ZipFile
import urllib.parse
from flask import Flask, send_from_directory, request

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
app = dash.Dash(__name__, suppress_callback_exceptions=True, 
                server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = 'GNPS - Library Explorer'

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
            html.Img(
                src="https://gnps2.org/static/img/logo.png", width="120px"),
            href="https://gnps2.org"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink(
                    "GNPS - Library Explorer - Version 0.1", href="#")),
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
                    dbc.InputGroupAddon(
                        "Peak Histogram Min intensity norm (out of 1.0)", addon_type="prepend"),
                    dbc.Input(id='intensitynormmin',
                              placeholder="intensitynormmin", value="0.05"),
                ],
                className="mb-3",
            ),
            html.Br(),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon(
                        "Peak Percent (out of 100)", addon_type="prepend"),
                    dbc.Input(id='percentoccurmin',
                              placeholder="percentoccurmin", value="20"),
                ],
                className="mb-3",
            ),
            dbc.Row([
                dbc.Button("Copy Link", block=True, color="info",
                           id="copy_link_button", n_clicks=0),
                dbc.Button("Download Filtered Table", block=True,
                           color="info", id="download_button", n_clicks=0),
                dcc.Download(id="download-filtered-data"),
            ]),
            html.Div(
                [
                    dcc.Link(id="query_link", href="#", target="_blank"),
                ],
                style={
                    "display": "none"
                }
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
            html.Div(
                id="SMILES_search",
                children=[
                    dcc.Input(
                        id="SMILES_text",
                        type="text",
                        placeholder="input SMILES",
                        style={"flex": 1, "align-self": "stretch"}
                    ),
                    html.Div(children=[
                        html.Img(
                            id="SMILES_preview_img",
                            src="https://images.freeimages.com/images/previews/b05/more-marbles-less-random-1483002.jpg",
                            height="150px",
                            width="300px",
                            style={"display": "none"}
                        ),
                        html.Div(id="SMILES_preview_text", children="Structure Preview", style = {"display": "block", "color": "darkgray", "width": "300px", "text-align": "center"})
                    ]),
                    dbc.Button("Filter Structures", color="info",
                               id="SMILES_button", n_clicks=0, style={"height": "50px"}),

                    # This is a hidden element to fire the call back only if the smile structure is parseable
                    html.P(id="SMILES_parsed_filter",
                           style={"display": "none"}),

                ],
                style={"display": "flex",
                       "flex-direction": "row", "align-items": "center", "margin": "10px", "min-height": "150px"}
            ),
            dcc.Loading(
                id="output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
            html.Br(),
            html.Hr(),
            dcc.Loading(
                id="spectrumrendering",
                children=[html.Div([html.Div(id="loading-output-25")])],
                type="default",
            ),
            html.Br(),
            dbc.Button("Update Histograms", block=True, color="info",
                       id="histogram_button", n_clicks=0),
            html.Hr(),
            dcc.Loading(
                id="plots",
                children=[html.Div([html.Div(id="loading-output-24")])],
                type="default",
            ),
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Mingxun Wang PhD - UC Riverside",
            html.Br(),
            html.Br(),
            html.H5("Citation"),
            html.A('Mingxun Wang, Jeremy J. Carver, Vanessa V. Phelan, Laura M. Sanchez, Neha Garg, Yao Peng, Don Duy Nguyen et al. "Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking." Nature biotechnology 34, no. 8 (2016): 828. PMID: 27504778',
                   href="https://www.nature.com/articles/nbt.3597"),
            html.Br(),
            html.Br(),
            html.A('Checkout our other work!', 
                href="https://www.cs.ucr.edu/~mingxunw/")
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


@app.callback(
    [Output('SMILES_preview_img', 'src'),
     Output('SMILES_preview_img', 'style'),
     Output('SMILES_preview_text', 'children'),
     Output('SMILES_preview_text', 'style'),
     Output('SMILES_parsed_filter', 'children')],
    Input('SMILES_button', 'n_clicks'),
    State('SMILES_text', 'value'), prevent_initial_call=True)
def update_output(clicks, input_value):
    if input_value is not None and len(input_value) > 0:
        try:
            # 'COC(=O)c1c[nH]c2cc(OC(C)C)c(OC(C)C)cc2c1=O'
            smiles = input_value
            buffered = BytesIO()
            d2d = rdMolDraw2D.MolDraw2DSVG(600, 600)
            opts = d2d.drawOptions()
            opts.clearBackground = False
            d2d.DrawMolecule(Chem.MolFromSmiles(smiles))
            d2d.FinishDrawing()
            img_str = d2d.GetDrawingText()
            buffered.write(str.encode(img_str))
            img_str = base64.b64encode(buffered.getvalue())
            img_str = f"data:image/svg+xml;base64,{repr(img_str)[2:-1]}"
            return [img_str, {"display": "block"}, "text", {"display": "none"}, input_value]
        except:
            return ["text", {"display": "none"}, "Parsing Error", {"display": "block", "color": "red", "width": "300px", "text-align": "center"}, ""]
    else:
        return ["text", {"display": "none"}, "Structure Preview", {"display": "block", "color": "darkgray", "width": "300px", "text-align": "center"}, ""]


@app.callback([
    Output('datatable', 'filter_query'),
    Output('intensitynormmin', 'value'),
],
    [Input('url', 'search')])
def determine_url_parameters(search):
    try:
        query_dict = urllib.parse.parse_qs(search[1:])
    except:
        query_dict = {}

    filter_query = _get_url_param(query_dict, "filter_query", dash.no_update)
    intensitynormmin = _get_url_param(
        query_dict, "intensitynormmin", dash.no_update)

    return [filter_query, intensitynormmin]


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

    blacklist_columns = ["spectrumid_int"]
    show_columns = [{"name": i, "id": i}
                    for i in sorted(results_list[0]) if i not in blacklist_columns]

    table_obj = dash_table.DataTable(
        id='datatable',
        columns=show_columns,
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
        Input('datatable', "filter_query"),
        Input('SMILES_parsed_filter', 'children'),
], prevent_initial_call=True)
def update_table(page_current, page_size, sort_by, filter, smiles_filter):
    query_parameters = {}
    query_parameters["page_current"] = page_current
    query_parameters["page_size"] = page_size
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter
    query_parameters["smiles_filter"] = smiles_filter

    try:
        if smiles_filter is not None and len(smiles_filter) > 0:
            result = tasks.task_query_data_with_smiles.delay(query_parameters)
        else:
            result = tasks.task_query_data.delay(query_parameters)
        results_list, results_count = result.get()
    except:
        return [[], [], 0, "Query Error"]

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
        Input('histogram_button', "n_clicks"),
],
    [
        State('datatable', "page_current"),
        State('datatable', "page_size"),
        State('datatable', 'sort_by'),
        State('datatable', "filter_query"),
        State('intensitynormmin', 'value'),
        State('percentoccurmin', 'value'),
        State('SMILES_parsed_filter', 'children')
], prevent_initial_call=True)
def update_table(n_clicks, page_current, page_size, sort_by, filter, intensitynormmin, percentoccurmin, smiles_filter):
    query_parameters = {}
    query_parameters["page_current"] = page_current
    query_parameters["page_size"] = page_size
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter
    query_parameters["smiles_filter"] = smiles_filter

    graph_config = {
        "toImageButtonOptions": {
            "format": "svg",
            'filename': 'plot',
            'height': None,
            'width': None,
        }
    }

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

    output_figure_list = ["Library Sizes", html.Br(), html.Br()]

    # Launching all the compute tasks
    histogram_result = tasks.plot_peak_histogram.delay(
        query_parameters, intensitynormmin=intensitynormmin)
    histogram_losses_result = tasks.plot_peakloss_histogram.delay(
        query_parameters, intensitynormmin=intensitynormmin)
    plot_peak_heatmap_result = tasks.plot_peak_heatmap.delay(query_parameters)
    box_plot_figure = tasks.plot_peak_boxplots.delay(
        query_parameters, intensitynormmin=intensitynormmin, percentoccurmin=percentoccurmin)
    box_plot_losses_figure = tasks.plot_peak_boxplots.delay(
        query_parameters, intensitynormmin=intensitynormmin, percentoccurmin=percentoccurmin, neutralloss=True)

    # Creating library size bar chart
    library_count_df = pd.DataFrame(library_count_result)
    library_count_df["numberspectra"] = library_count_df['EXPR$1']
    library_count_fig = px.bar(library_count_df, y='library_membership',
                               x='numberspectra', log_x=True, orientation="h", height=800)

    output_figure_list.append(dcc.Graph(figure=library_count_fig))
    output_figure_list.append(html.Br())

    # Creating histogram by m/z
    histogram_result = histogram_result.get()

    histogram_df = pd.DataFrame(histogram_result)
    histogram_fig = px.bar(x=histogram_df["mz"], y=histogram_df["counts"], labels={
                           'x': "mz", 'y': 'count'}, title="Peak Histogram")
    histogram_fig.update_layout(bargap=0)
    histogram_fig.update_traces(marker=dict(line=dict(width=0)))

    output_figure_list.append(dcc.Graph(figure=histogram_fig))
    output_figure_list.append(html.Br())

    # Creating histogram by m/z loss
    histogram_losses_result = histogram_losses_result.get()

    histogram_loss_df = pd.DataFrame(histogram_losses_result)
    histogram_loss_fig = px.bar(x=histogram_loss_df["mz_nl"], y=histogram_loss_df["counts"], labels={
                                'x': "mz_nl", 'y': 'count'}, title="Peak Loss Histogram")
    histogram_loss_fig.update_layout(bargap=0)
    histogram_loss_fig.update_traces(marker=dict(line=dict(width=0)))

    output_figure_list.append(
        dcc.Graph(figure=histogram_loss_fig, config=graph_config))
    output_figure_list.append(html.Br())

    # Creating an m/z histogram mirror plot
    mz_intensity = list(histogram_df["counts"])
    mz_list = list(histogram_df["mz"])

    nl_intensity = list(histogram_loss_df["counts"])
    nl_intensity = [i * -1 for i in nl_intensity]
    nl_mz_list = list(histogram_loss_df["mz_nl"])

    merged_mz = mz_list + nl_mz_list
    merged_intensity = mz_intensity + nl_intensity
    merged_neg_intensity = [i * -1 for i in merged_intensity]

    mirror_fig = go.Figure(
        data=go.Scatter(x=merged_mz, y=merged_intensity,
                        mode='markers',
                        marker=dict(size=1),
                        error_y=dict(
                            symmetric=False,
                            arrayminus=[0]*len(merged_neg_intensity),
                            array=merged_neg_intensity,
                            width=0,
                            thickness=3
                        ),
                        hoverinfo="x",
                        text=merged_mz
                        )
    )

    mirror_fig.update_yaxes(
        zeroline=True, zerolinewidth=1, zerolinecolor='Black')
    mirror_fig.update_layout(template="plotly_white")
    mirror_fig.update_xaxes(
        title_text='m/z (positive), neutral loss m/z (negative)')
    mirror_fig.update_yaxes(title_text='counts')

    output_figure_list.append(
        dcc.Graph(figure=mirror_fig, config=graph_config))
    output_figure_list.append(html.Br())

    # Creating heatmap
    plot_peak_heatmap_result = plot_peak_heatmap_result.get()
    aggregation = xr.DataArray.from_dict(plot_peak_heatmap_result)
    heatmap_fig = px.imshow(aggregation, origin='lower', labels={
                            'color': 'peak intensity'}, height=600)

    output_figure_list.append(
        dcc.Graph(figure=heatmap_fig, config=graph_config))
    output_figure_list.append(html.Br())

    # Creating box plots
    box_plot_figure = box_plot_figure.get()

    if box_plot_figure is not None:
        output_figure_list.append(
            dcc.Graph(figure=box_plot_figure, config=graph_config))
        output_figure_list.append(html.Br())

    # Creating neutral loss box plots
    box_plot_losses_figure = box_plot_losses_figure.get()

    if box_plot_losses_figure is not None:
        output_figure_list.append(
            dcc.Graph(figure=box_plot_losses_figure, config=graph_config))
        output_figure_list.append(html.Br())

    # Creating histogram by neutral loss
    # result = tasks.plot_peakloss_histogram.delay(query_parameters, intensitynormmin=intensitynormmin)
    # result = result.get()
    # histogram_loss_df = pd.DataFrame(result)
    # histogram_loss_fig = px.bar(x=histogram_loss_df["nl_mz"], y=histogram_loss_df["counts"], labels={'x': "nl_mz", 'y':'count'}, title="Neutral Loss Peak Histogram")
    # histogram_loss_fig.update_layout(bargap=0)
    # histogram_loss_fig.update_traces(marker=dict(line=dict(width=0)))
    # dcc.Graph(figure=histogram_loss_fig)

    return [output_figure_list]


@app.callback([
    Output('spectrumrendering', 'children')
],
    [
    Input('datatable', 'derived_virtual_data'),
    Input('datatable', 'derived_virtual_selected_rows'),
], prevent_initial_call=True
)
def draw_spectrum(table_data, table_selected):
    try:
        selected_row = table_data[table_selected[0]]
    except:
        return ["Choose Library Spectrum to Show Spectra"]

    selected_usi = "mzspec:GNPS:GNPS-LIBRARY:accession:" + \
        selected_row["spectrum_id"]

    mirror_plot_params = {
        'usi1': selected_usi,
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

    usi_url = "https://metabolomics-usi.gnps2.org/"

    img_obj = html.Img(src=usi_url + "svg?" + url_params)
    img_link_url = html.A(img_obj, href=usi_url +
                          "dashinterface?" + url_params, target="_blank")
    usi_link_url = html.A(selected_usi, href=usi_url +
                          "dashinterface?" + url_params, target="_blank")

    return [[usi_link_url, html.Br(), img_link_url]]


@app.callback(
    [
        Output("download-filtered-data", "data"),
    ],
    [
        Input("download_button", "n_clicks"),
    ],
    [
        State('datatable', 'sort_by'),
        State('datatable', "filter_query")
    ],
    prevent_initial_call=True
)
def download_data(n_clicks, sort_by, filter_query):
    query_parameters = {}
    query_parameters["page_current"] = 0
    query_parameters["page_size"] = 1000000
    query_parameters["sort_by"] = sort_by
    query_parameters["filter"] = filter_query

    try:
        result = tasks.task_query_bigdata.delay(query_parameters)
        results_list, results_count = result.get()
    except:
        raise

    df = pd.DataFrame(results_list)

    return [dcc.send_data_frame(df.to_csv, "filtered_library.csv")]


@app.callback([
    Output('query_link', 'href'),
],
    [
    Input('datatable', 'filter_query'),
    Input('intensitynormmin', 'value'),
], prevent_initial_call=True)
def draw_url(filter_query, intensitynormmin):
    params = {}
    params["filter_query"] = filter_query
    params["intensitynormmin"] = intensitynormmin

    url_params = urllib.parse.urlencode(params)

    return [request.host_url + "/?" + url_params]


app.clientside_callback(
    """
    function(n_clicks, button_id, text_to_copy) {
        original_text = "Copy Link"
        if (n_clicks > 0) {
            const el = document.createElement('textarea');
            el.value = text_to_copy;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
            setTimeout(function(id_to_update, text_to_update){ 
                return function(){
                    document.getElementById(id_to_update).textContent = text_to_update
                }}(button_id, original_text), 1000);
            document.getElementById(button_id).textContent = "Copied!"
            return 'Copied!';
        } else {
            return original_text;
        }
    }
    """,
    Output('copy_link_button', 'children'),
    [
        Input('copy_link_button', 'n_clicks'),
        Input('copy_link_button', 'id'),
    ],
    [
        State('query_link', 'href'),
    ]
)


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
