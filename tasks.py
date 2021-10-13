from celery import Celery
import glob
import os
import sys
import shutil
import pandas as pd
import pyarrow as pa
import requests
from utils import load_data_gnps_json

from pyomnisci import connect

def get_connection():
    connection = connect(user="admin", password="HyperInteractive", host="gnpslibrary-omniscidb", dbname="omnisci")
    return connection

celery_instance = Celery('tasks', backend='redis://gnpslibrary-redis', broker='pyamqp://guest@gnpslibrary-rabbitmq//', )


def _construct_df_selections(df, parameters):
    """Applying filtering on the vaex dataframe lazily

    Args:
        df ([type]): [description]
        parameters ([type]): [description]

    Returns:
        [type]: [description]
    """

    try:
        filter = parameters.get("filter", "")
        filtering_expressions = filter.split(' && ')

        for filter_part in filtering_expressions:
            filter_splits = filter_part.split(" ")
            column_part = filter_splits[0]
            operator = filter_splits[1]
            value_part = filter_splits[2]

            if operator == "contains":
                # Checking the type of the column
                truncated_df = df.head().to_pandas_df()
                if pd.api.types.is_integer_dtype(truncated_df[column_part[1:-1]].dtype):
                    df = df[df[column_part[1:-1]].isin([int(value_part)])]
                else:
                    df = df[df[column_part[1:-1]].str.contains(value_part.lower())]

            if operator == ">":
                # we know its numerical
                df = df[df[column_part[1:-1]] > float(value_part)]

            if operator == "<":
                # we know its numerical
                df = df[df[column_part[1:-1]] < float(value_part)]
    except:
        pass

    return df


@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"

@celery_instance.task(time_limit=3600)
def task_library_download():
    library_list = requests.get("https://gnps-external.ucsd.edu/gnpslibrary.json").json()

    for library_obj in library_list:
        print("Loading", library_obj)

        library_url = "https://gnps-external.ucsd.edu/gnpslibrary/{}.json".format(library_obj["library"])
        library_spectra_list = requests.get(library_url).json()

        # Read into pandas without peaks and inject into database
        library_df = pd.DataFrame(library_spectra_list)
        library_df = library_df[["spectrum_id", 
                                 "library_membership", 
                                 "submit_user", 
                                 "Pubmed_ID", 
                                 "PI", 
                                 "Data_Collector", 
                                 "Ion_Mode", 
                                 "Precursor_MZ", 
                                 "Compound_Name",
                                 "Instrument",
                                 "Adduct",
                                 "Charge",
                                 "Formula_smiles"]]

        library_df["Precursor_MZ"] = library_df["Precursor_MZ"].astype(float)

        # Putting into ominisci
        table_name = "gnpslibrary"
        con = get_connection()
        try:
            # Creating table
            con.create_table(table_name, library_df)
        except:
            pass

        # Cleaning up table
        omni_cursor = con.cursor()
        query = "DELETE FROM {} WHERE library_membership='{}';".format(table_name, library_obj["library"])
        omni_cursor.execute(query)

        # Loading data
        pa_df = pa.Table.from_pandas(library_df)
        con.load_table_arrow(table_name, pa_df)

        # Creating lower cases for certain columns
        to_lower_columns = ["library_membership", "submit_user", "Ion_Mode", "Instrument", "Pubmed_ID", "PI", "Data_Collector", "Adduct", "Formula_smiles", "Compound_Name"]
        for column in to_lower_columns:
            library_df[column] = library_df[column].str.lower()

        # Saving Feather
        output_feather = "./temp/" + "table_{}.feather".format(library_obj["library"])
        library_df.reset_index().to_feather(output_feather, compression="uncompressed")

        # Saving Peak Feather
        def divide_chunks(l, n):  
            # looping till length l
            for i in range(0, len(l), n): 
                yield l[i:i + n]

        spectra_split = list(divide_chunks(library_spectra_list, 10000))
        for i, spectra_list in enumerate(spectra_split):
            output_feather = "./temp/" + "peak_{}_{}.feather".format(library_obj["library"], i)
            peaks_df = load_data_gnps_json(spectra_list)
            peaks_df.reset_index().to_feather(output_feather, compression="uncompressed")


@celery_instance.task(time_limit=30)
def task_query_data(parameters):
    table_name = "gnpslibrary"

    page_size = parameters.get("page_size", 20)
    sql_query = "SELECT * FROM {}".format(table_name)
    sql_count = "SELECT count(*) FROM {}".format(table_name)
    sql_count_suffix = ""
    sql_query_suffix = ""

    print(parameters)
    
    # Trying to do filtering
    try:
        filter = parameters.get("filter", "")
        filtering_expressions = filter.split(' && ')
        where_clauses = []
        for filter_part in filtering_expressions:
            filter_splits = filter_part.split(" ")
            column_part = filter_splits[0]
            operator = filter_splits[1]
            value_part = filter_splits[2]

            if operator == "contains":
                #where_clauses.append("{} LIKE '%{}%'".format(column_part[1:-1], value_part))
                # Case insensitive
                where_clauses.append("{} ILIKE '%{}%'".format(column_part[1:-1], value_part))


            if operator == ">":
                # we know its numerical
                where_clauses.append("{} > {}".format(column_part[1:-1], float(value_part)))

            if operator == "<":
                # we know its numerical
                where_clauses.append("{} < {}".format(column_part[1:-1], float(value_part)))

        if len(where_clauses) > 0:
            sql_query_suffix += " WHERE " + " AND ".join(where_clauses)
            sql_count_suffix += " WHERE " + " AND ".join(where_clauses)
            
    except:
        pass

    # Trying to do sorting
    try:
        # Using these sort by columns
        sort_column_dict = parameters["sort_by"][0]
        sort_column = sort_column_dict["column_id"]
        sort_direction = sort_column_dict["direction"]

        sql_query_suffix += " ORDER BY {} {}".format(sort_column, sort_direction.upper())
    except:
        pass
    
    # Limiting the query
    sql_query_suffix += " LIMIT {} OFFSET {}".format(page_size, parameters.get("page_current", 0) * page_size)

    # Making sure the connection is good
    print(sql_query)
    con = get_connection()
    results_df = pd.read_sql(sql_query + sql_query_suffix, con)

    # Counting total records
    results_count_df = pd.read_sql(sql_count + sql_count_suffix, con)
    results_count = int(results_count_df.iloc[0][0])

    return results_df.to_dict(orient="records"), results_count

@celery_instance.task(time_limit=30)
def query_library_counts():
    con = get_connection()

    table_name = "gnpslibrary"
    histogram_df = pd.read_sql("SELECT library_membership, count(*) FROM {} GROUP BY library_membership".format(table_name), con)

    return histogram_df.to_dict(orient="records")

import vaex as vx
import numpy as np

@celery_instance.task(time_limit=60)
def plot_peak_histogram(parameters, intensitynormmin=0):
    table_df = vx.open("./temp/" + 'table_*.feather') 
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan', right_on='spectrum_id', how='inner')

    # Filtering other criteria
    peak_df = peak_df[peak_df["i_norm"] > float(intensitynormmin)]

    minmaxx = peak_df.minmax(["mz"])

    mass_difference = int(minmaxx[0][1] - minmaxx[0][0])
    
    xcounts = peak_df.count(binby=[peak_df["mz"]], shape=(mass_difference))    

    histogram_df = pd.DataFrame()
    histogram_df["counts"] = xcounts
    histogram_df["mz"] = np.linspace(minmaxx[0][0], minmaxx[0][1], mass_difference)

    return histogram_df.to_dict(orient="records")

@celery_instance.task(time_limit=60)
def plot_peakloss_histogram(parameters, intensitynormmin=0):
    table_df = vx.open("./temp/" + 'table_*.feather') 
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan', right_on='spectrum_id', how='inner')

    # Filtering other criteria
    peak_df = peak_df[peak_df["i_norm"] > float(intensitynormmin)]

    # Calculating the loss values
    peak_df["nl_mz"] = peak_df["precmz"] - peak_df["mz"]

    minmaxx = peak_df.minmax(["nl_mz"])

    mass_difference = int(minmaxx[0][1] - minmaxx[0][0])
    
    xcounts = peak_df.count(binby=[peak_df["nl_mz"]], shape=(mass_difference))    

    histogram_df = pd.DataFrame()
    histogram_df["counts"] = xcounts
    histogram_df["nl_mz"] = np.linspace(minmaxx[0][0], minmaxx[0][1], mass_difference)

    return histogram_df.to_dict(orient="records")


@celery_instance.task(time_limit=60)
def plot_peak_heatmap(parameters):
    table_df = vx.open("./temp/" + 'table_*.feather') 
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan', right_on='spectrum_id', how='inner')

    peak_df = peak_df[peak_df["mz"] < 1000]

    # All scan values
    scan_values = peak_df["scan"].unique()
    scan_to_int_mapping_df = pd.DataFrame()
    scan_to_int_mapping_df["scan"] = scan_values
    scan_to_int_mapping_df["spectrum"] = scan_to_int_mapping_df.index
    scan_to_int_mapping_df = vx.from_pandas(scan_to_int_mapping_df)

    peak_df = peak_df.join(scan_to_int_mapping_df, left_on='scan', right_on='scan', how='inner')

    aggregation = peak_df.sum("i_norm", binby=[peak_df["spectrum"], peak_df["mz"]], shape=(128, 128), array_type="xarray")

    return aggregation.to_dict()
    

# celery_instance.conf.beat_schedule = {
#     "cleanup": {
#         "task": "tasks._task_cleanup",
#         "schedule": 3600
#     }
# }


celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'worker'},
    'tasks.task_query_data': {'queue': 'worker'},
    'tasks.query_library_counts': {'queue': 'worker'},
    'tasks.plot_peak_histogram': {'queue': 'worker'},
    'tasks.plot_peakloss_histogram': {'queue': 'worker'},
    'tasks.plot_peak_heatmap': {'queue': 'worker'},
    
    
    'tasks.task_library_download': {'queue': 'workerload'},
}

celery_instance.conf.beat_schedule = {
    "cleanup": {
        "task": "tasks.task_library_download",
        "schedule": 300
    }
}