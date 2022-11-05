from re import S
import vaex as vx
import numpy as np
from celery import Celery
import glob
import os
import sys
import shutil
import pandas as pd
import pyarrow as pa
import plotly.express as px
import requests
from utils import load_data_gnps_json
from rdkit import Chem
from rdkit.rdBase import BlockLogs

from pyomnisci import connect

smiles_map = {}

def update_map():
    df = vx.open("./temp/" + 'table_*.feather')
    df = df.to_pandas_df()
    smiles = df['Smiles'].tolist()
    block = BlockLogs()
    for i in range(len(smiles)):
        if smiles[i] in smiles_map:
            smiles_map[smiles[i]][0].append(i)
        else:
            try:
                m = Chem.MolFromSmiles(smiles[i])
                smiles_map[smiles[i]] = [[i], m]
            except:
                smiles_map[smiles[i]] = [[i], None]
    del block

def get_connection():
    connection = connect(user="admin", password="HyperInteractive",
                         host="gnpslibrary-omniscidb", dbname="omnisci")
    return connection


celery_instance = Celery('tasks', backend='redis://gnpslibrary-redis',
                         broker='pyamqp://guest@gnpslibrary-rabbitmq//', )

celery_instance.conf.update(
    task_serializer="pickle",
    result_serializer="pickle",
    accept_content=["pickle", "json"],
)


def _construct_df_selections(df, parameters):
    """Applying filtering on the vaex dataframe lazily

    Args:
        df ([type]): [description]
        parameters ([type]): [description]

    Returns:
        [type]: [description]
    """
    if parameters["smiles_filter"] is not None and len(parameters["smiles_filter"]) > 0:
        if len(smiles_map.keys()) == 0:
            update_map()
        
        # move the rdkit logs to 'block' to increase speed
        block = BlockLogs()
        
        # 'filter_mol' contains the Mol representation of the filter
        filter_mol = Chem.MolFromSmiles(parameters["smiles_filter"])
        
        # for each SMILES representation, if it contains the filter we add the index of all its occurances to the matched array
        matches = []
        for smile in smiles_map:
            try:
                temp_mol = smiles_map[smile][1]
                if temp_mol.HasSubstructMatch(filter_mol):
                    matches.extend(smiles_map[smile][0])
            except:
                pass
        
        #delete the logs
        del block
        
        # Add a virtual column to the dataframe 
        df['index'] = vx.vrange(0, len(df))

        # filter df based on matches
        df = df[df.index.isin(matches)]

    try:
        filter = parameters.get("filter", "")
        filtering_expressions = filter.split(' && ')

        for filter_part in filtering_expressions:
            filter_splits = filter_part.split(" ")
            column_part = filter_splits[0]
            operator = filter_splits[1]
            value_part = filter_splits[2]

            if operator == "contains" or operator == "scontains":
                # Checking the type of the column
                truncated_df = df.head().to_pandas_df()
                if pd.api.types.is_integer_dtype(truncated_df[column_part[1:-1]].dtype):
                    df = df[df[column_part[1:-1]].isin([int(value_part)])]
                else:
                    df = df[df[column_part[1:-1]
                               ].str.contains(value_part.lower())]

            if operator == ">":
                # we know its numerical
                df = df[df[column_part[1:-1]] > float(value_part)]

            if operator == "<":
                # we know its numerical
                df = df[df[column_part[1:-1]] < float(value_part)]
    except:
        pass

    return df


# Here we will read the feather data and plot a box plot to understand variability
@celery_instance.task(time_limit=60)
def plot_peak_boxplots(parameters, intensitynormmin=0, percentoccurmin=20, neutralloss=False):

    table_df = vx.open("./temp/" + 'table_*.feather')
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan',
                           right_on='spectrum_id', how='inner')

    if len(peak_df) > 10000000:
        return None

    # Make vaex dataframe into pandas dataframe
    peak_df = peak_df.to_pandas_df()

    # Binning MZ values
    if neutralloss is False:
        peak_df['mz_binned'] = peak_df['mz'].astype('int')
    else:
        peak_df['mz_binned'] = peak_df['mz_nl'].astype('int')
    unique_mz_binned = peak_df['mz_binned'].unique()

    # Calculating ratio of scans that DO NOT have a value at mz_binned
    no_peak_ratio = {}
    contains_peak_ratio = {}

    for peak in unique_mz_binned:
        mz_df = peak_df[peak_df["mz_binned"] == peak]
        all_peaks = mz_df['i_norm'].values

        above = sum(i >= float(intensitynormmin) for i in all_peaks)
        below = sum(i < float(intensitynormmin) for i in all_peaks)

        total_scans = len(mz_df)

        no_peak_ratio[peak] = below/total_scans

        if above/total_scans >= (float(percentoccurmin)/100):
            contains_peak_ratio[peak] = above/total_scans

    # Make dataframe from above calculations
    peak_ratio_df = pd.DataFrame.from_dict(no_peak_ratio, orient='index')
    peak_ratio_df.index.name = 'mz_binned'
    peak_ratio_df = peak_ratio_df.rename(columns={0: "ratio of missing peaks"})
    peak_ratio_df['ratio of present peaks'] = peak_ratio_df.index.map(
        contains_peak_ratio)

    # Filter original peak_df
    filtered_peak_df = peak_df[peak_df["i_norm"] > float(intensitynormmin)]

    # Filtering to only include peaks that are present in at least 20% of the scans
    filtered_peak_df = filtered_peak_df[filtered_peak_df["mz_binned"].isin(
        contains_peak_ratio.keys())]

    ax = px.box(filtered_peak_df, x='mz_binned', y='i_norm')
    ax.add_bar(x=peak_ratio_df.index, y=-peak_ratio_df["ratio of present peaks"],
               name="ratio of spectra where at least " + str(percentoccurmin)+"% contain peak")
    if neutralloss is False:
        ax.update_layout(title_text="MS/MS Peak Intensity Distribution")
    else:
        ax.update_layout(
            title_text="MS/MS Neutral Loss Peak Intensity Distribution")

    return ax


@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"


@celery_instance.task(time_limit=3600)
def task_library_download():
    library_list = requests.get(
        "https://gnps-external.ucsd.edu/gnpslibrary.json").json()

    for library_obj in library_list:

        library_url = "https://gnps-external.ucsd.edu/gnpslibrary/{}.json".format(
            library_obj["library"])
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
                                 "Smiles",
                                 "InChIKey_smiles", "InChIKey_inchi", "Formula_smiles", "Formula_inchi"]]

        library_df["Precursor_MZ"] = library_df["Precursor_MZ"].astype(float)
        library_df["spectrumid_int"] = library_df["spectrum_id"].str.replace(
            "CCMSLIB", "").astype(int)

        # Putting into ominisci
        table_name = "gnpslibrary"
        con = get_connection()
        omni_cursor = con.cursor()
        try:
            # Creating table
            con.create_table(table_name, library_df)
        except Exception as e:
            pass

        # Cleaning up table
        # omni_cursor = con.cursor()
        query = "DELETE FROM {} WHERE library_membership='{}';".format(
            table_name, library_obj["library"])
        omni_cursor.execute(query)

        # Loading data
        pa_df = pa.Table.from_pandas(library_df)
        con.load_table_arrow(table_name, pa_df)

        # Creating lower cases for certain columns
        to_lower_columns = ["library_membership", "submit_user", "Ion_Mode",
                            "Instrument", "Pubmed_ID", "PI", "Data_Collector", "Compound_Name"]
        for column in to_lower_columns:
            library_df[column] = library_df[column].str.lower()

        # Saving Feather
        output_feather = "./temp/" + \
            "table_{}.feather".format(library_obj["library"])
        library_df.reset_index().to_feather(output_feather, compression="uncompressed")

        # Saving Peak Feather
        def divide_chunks(l, n):
            # looping till length l
            for i in range(0, len(l), n):
                yield l[i:i + n]

        spectra_split = list(divide_chunks(library_spectra_list, 10000))
        for i, spectra_list in enumerate(spectra_split):
            output_feather = "./temp/" + \
                "peak_{}_{}.feather".format(library_obj["library"], i)
            peaks_df = load_data_gnps_json(spectra_list)
            peaks_df.reset_index().to_feather(output_feather, compression="uncompressed")
    
    update_map()


@celery_instance.task(time_limit=30)
def task_query_data(parameters):
    table_name = "gnpslibrary"

    page_size = parameters.get("page_size", 20)
    sql_query = "SELECT * FROM {}".format(table_name)
    sql_count = "SELECT count(*) FROM {}".format(table_name)
    sql_count_suffix = ""
    sql_query_suffix = ""

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

            if operator == "contains" or operator == "scontains":
                #where_clauses.append("{} LIKE '%{}%'".format(column_part[1:-1], value_part))
                # Case insensitive
                where_clauses.append("{} ILIKE '%{}%'".format(
                    column_part[1:-1], value_part))

            if operator == ">":
                # we know its numerical
                where_clauses.append("{} > {}".format(
                    column_part[1:-1], float(value_part)))

            if operator == "<":
                # we know its numerical
                where_clauses.append("{} < {}".format(
                    column_part[1:-1], float(value_part)))


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

        sql_query_suffix += " ORDER BY {} {}".format(
            sort_column, sort_direction.upper())
    except:
        # Default sorting by spectrumid
        sql_query_suffix += " ORDER BY {} {}".format("spectrumid_int", "DESC")
        pass

    # Limiting the query
    sql_query_suffix += " LIMIT {} OFFSET {}".format(
        page_size, parameters.get("page_current", 0) * page_size)

    # Making sure the connection is good
    con = get_connection()
    results_df = pd.read_sql(sql_query + sql_query_suffix, con)

    # Counting total records
    results_count_df = pd.read_sql(sql_count + sql_count_suffix, con)
    results_count = int(results_count_df.iloc[0][0])

    return results_df.to_dict(orient="records"), results_count


@celery_instance.task(time_limit=30)
def task_query_data_with_smiles(parameters):
    page_size = parameters.get("page_size", 20)
    table_df = vx.open("./temp/" + 'table_*.feather')

    #applying the filters
    table_df = _construct_df_selections(table_df, parameters)
    
    #changing from local vaex local dataframe to dataframe to support sort
    table_df = table_df.to_pandas_df()
    
    # Trying to do sorting
    try:
        # Using these sort by columns
        sort_column_dict = parameters["sort_by"][0]
        sort_column = sort_column_dict["column_id"]
        sort_direction = sort_column_dict["direction"]

        table_df = table_df.sort_values(by=sort_column, ascending=(
            sort_direction.upper() == "ASC"))
    except:
        # Default sorting by spectrumid
        table_df = table_df.sort_values(by="spectrumid_int", ascending=False)
        pass

    results_count = len(table_df.index)
    table_df = table_df[parameters.get("page_current", 0) * page_size:
                        (parameters.get("page_current", 0)+1) * page_size]
    return table_df.to_dict(orient="records"), results_count


@celery_instance.task(time_limit=120)
def task_query_bigdata(parameters):
    table_df = vx.open("./temp/" + 'table_*.feather')
    table_df = _construct_df_selections(table_df, parameters)

    table_df = table_df.to_pandas_df()

    return table_df.to_dict(orient="records"), len(table_df)


@celery_instance.task(time_limit=30)
def query_library_counts():
    con = get_connection()

    table_name = "gnpslibrary"
    histogram_df = pd.read_sql(
        "SELECT library_membership, count(*) FROM {} GROUP BY library_membership".format(table_name), con)

    return histogram_df.to_dict(orient="records")


@celery_instance.task(time_limit=60)
def plot_peak_histogram(parameters, intensitynormmin=0, neutralloss=False):
    table_df = vx.open("./temp/" + 'table_*.feather')
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan',
                           right_on='spectrum_id', how='inner')

    # Filtering other criteria
    peak_df = peak_df[peak_df["i_norm"] > float(intensitynormmin)]

    data_column = "mz"
    if neutralloss:
        data_column = "mz_nl"

    minmaxx = peak_df.minmax([data_column])

    mass_difference = int(minmaxx[0][1] - minmaxx[0][0])

    xcounts = peak_df.count(
        binby=[peak_df[data_column]], shape=(mass_difference))

    histogram_df = pd.DataFrame()
    histogram_df["counts"] = xcounts
    histogram_df[data_column] = np.linspace(
        minmaxx[0][0], minmaxx[0][1], mass_difference)

    return histogram_df.to_dict(orient="records")


@celery_instance.task(time_limit=60)
def plot_peakloss_histogram(parameters, intensitynormmin=0):
    return plot_peak_histogram(parameters, intensitynormmin=intensitynormmin, neutralloss=True)


@celery_instance.task(time_limit=60)
def plot_peak_heatmap(parameters):
    table_df = vx.open("./temp/" + 'table_*.feather')
    table_df = _construct_df_selections(table_df, parameters)
    table_df = table_df[["spectrum_id"]]

    # Merging the spectra
    peak_df = vx.open("./temp/" + 'peak_*.feather')
    peak_df = peak_df.join(table_df, left_on='scan',
                           right_on='spectrum_id', how='inner')

    peak_df = peak_df[peak_df["mz"] < 1000]

    # All scan values
    scan_values = peak_df["scan"].unique()
    scan_to_int_mapping_df = pd.DataFrame()
    scan_to_int_mapping_df["scan"] = scan_values
    scan_to_int_mapping_df["spectrum"] = scan_to_int_mapping_df.index
    scan_to_int_mapping_df = vx.from_pandas(scan_to_int_mapping_df)

    peak_df = peak_df.join(scan_to_int_mapping_df,
                           left_on='scan', right_on='scan', how='inner')

    aggregation = peak_df.sum("i_norm", binby=[
                              peak_df["spectrum"], peak_df["mz"]], shape=(128, 128), array_type="xarray")

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
    'tasks.task_query_data_with_smiles': {'queue': 'worker'},
    'tasks.task_query_bigdata': {'queue': 'worker'},
    'tasks.query_library_counts': {'queue': 'worker'},
    'tasks.plot_peak_histogram': {'queue': 'worker'},
    'tasks.plot_peakloss_histogram': {'queue': 'worker'},
    'tasks.plot_peak_boxplots': {'queue': 'worker'},
    'tasks.plot_peak_heatmap': {'queue': 'worker'},


    'tasks.task_library_download': {'queue': 'workerload'},
}

celery_instance.conf.beat_schedule = {
    "cleanup": {
        "task": "tasks.task_library_download",
        "schedule": 300
    }
}
