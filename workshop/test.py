import vaex as vx
import xarray as xr
import plotly.express as px
import pandas as pd

def test():
    peak_df = vx.open("../temp/" + 'peak_*.feather')

    table_df = vx.open("../temp/" + 'table_*.feather') 
    table_df = table_df[table_df["Compound_Name"].str.contains("Carnitine")]
    table_df = table_df[["spectrum_id"]]

    peak_df = peak_df.join(table_df, left_on='scan', right_on='spectrum_id', how='inner')
    peak_df = peak_df[peak_df["mz"] < 1000]

    # All scan values
    scan_values = peak_df["scan"].unique()
    scan_to_int_mapping_df = pd.DataFrame()
    scan_to_int_mapping_df["scan"] = scan_values
    scan_to_int_mapping_df["spectrum"] = scan_to_int_mapping_df.index
    scan_to_int_mapping_df = vx.from_pandas(scan_to_int_mapping_df)

    peak_df = peak_df.join(scan_to_int_mapping_df, left_on='scan', right_on='scan', how='inner')

    print(len(peak_df))
    aggregation = peak_df.sum("i_norm", binby=[peak_df["spectrum"], peak_df["mz"]], shape=(128, 128), array_type="xarray")

    fig = px.imshow(aggregation, origin='lower', labels={'color':'peak intensity'}, height=600)
    fig.write_image("test.png")



test()