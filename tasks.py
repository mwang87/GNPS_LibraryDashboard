from celery import Celery
import glob
import os
import sys
import shutil
import pandas as pd
import pyarrow as pa
import requests

from pyomnisci import connect

def get_connection():
    connection = connect(user="admin", password="HyperInteractive", host="gnpslibrary-omniscidb", dbname="omnisci")
    return connection

celery_instance = Celery('tasks', backend='redis://gnpslibrary-redis', broker='pyamqp://guest@gnpslibrary-rabbitmq//', )

@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"

@celery_instance.task(time_limit=3600)
def library_download():
    library_list = requests.get("https://gnps-external.ucsd.edu/gnpslibrary.json").json()

    for library_obj in library_list:
        library_url = "https://gnps-external.ucsd.edu/gnpslibrary/{}.json".format(library_obj["library"])
        print(library_url)
        library_spectra_list = requests.get(library_url).json()
        
        # Read into pandas without peaks and inject into database
    
    

    # # Making sure the connection is good
    # try:
    #     all_tables = con.get_tables()   
    # except:
    #     # Probably a bad connection
    #     con = get_connection()
    #     print("RETRYING CONNECTION")
        
    # all_tables = con.get_tables()
    # print(all_tables)

    # if table_name in all_tables:
    #     return "DONE"

    # task = usi.split(":")[2].split("-")[1]
    # file_path = usi.split(":")[2].split("-")[2]

    # temp_tsv = output_feather + ".tsv"

    # # TODO: chunk this
    # url = "https://proteomics2.ucsd.edu/ProteoSAFe/DownloadResultFile?task={}&file={}&block=main&process_html=false".format(task, file_path)
    # # Put file locally
    # with requests.get(url, stream=True) as r:
    #     with open(temp_tsv, 'wb') as f:
    #         shutil.copyfileobj(r.raw, f)

    # for chunk_df in pd.read_csv(temp_tsv, sep="\t", chunksize=100000):
    #     # Putting into ominisci
    #     try:
    #         # Creating table
    #         con.create_table(table_name, chunk_df)
    #     except:
    #         pass

    #     # Loading data
    #     pa_df = pa.Table.from_pandas(chunk_df)
    #     con.load_table_arrow(table_name, pa_df)
    
    # # TODO: Cleanup 
    
    # return "DONE"

@celery_instance.task(time_limit=30)
def query_data(usi, parameters):
    table_name = get_table_name(usi)

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
                where_clauses.append("{} LIKE '%{}%'".format(column_part[1:-1], value_part))

            print(filter_splits)
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
    try:
        all_tables = con.get_tables()   
    except:
        # Probably a bad connection
        con = get_connection()
        print("RETRYING CONNECTION")

    
    print(sql_query)
    results_df = pd.read_sql(sql_query + sql_query_suffix, con)

    # Counting total records
    results_count_df = pd.read_sql(sql_count + sql_count_suffix, con)
    results_count = int(results_count_df.iloc[0][0])

    return results_df.to_dict(orient="records"), results_count

@celery_instance.task(time_limit=30)
def query_histogram(usi, parameters):
    table_name = get_table_name(usi)

    # Making sure the connection is good
    try:
        all_tables = con.get_tables()   
    except:
        # Probably a bad connection
        con = get_connection()
        print("RETRYING CONNECTION")

    # USE THIS INSTEAD

    histogram_query = """SELECT
        CASE
            WHEN precmz <= 200 THEN "0-200"
            WHEN precmz <= 400 THEN "201-400"
            WHEN precmz <= 500 THEN "401-500"
            ELSE "501-"
        END as HISTGROUP,
        count(*) as count
    GROUP BY HISTGROUP 
    ORDER BY HISTGROUP;"""
    histogram_df = pd.read_sql(histogram_query, con)

    print(histogram_df)

    return ""


    

# celery_instance.conf.beat_schedule = {
#     "cleanup": {
#         "task": "tasks._task_cleanup",
#         "schedule": 3600
#     }
# }


celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'worker'},
    'tasks.task_download': {'queue': 'worker'},
    'tasks.query_data': {'queue': 'worker'},
    'tasks.query_histogram': {'queue': 'worker'},
    
}