from tqdm import tqdm
import pandas as pd
import json

def load_data_gnps_json(all_spectra):
    ms2_df_list = []

    for spectrum in tqdm(all_spectra):
        # Skipping spectra bigger than 1MB of peaks
        if len(spectrum["peaks_json"]) > 1000000:
            continue

        peaks = json.loads(spectrum["peaks_json"])
        peaks = [peak for peak in peaks if peak[1] > 0]
        if len(peaks) == 0:
            continue
        i_max = max([peak[1] for peak in peaks])
        i_sum = sum([peak[1] for peak in peaks])
        if i_max == 0:
            continue

        ms2mz_list = []

        for peak in peaks:
            peak_dict = {}
            peak_dict["i"] = peak[1]
            peak_dict["i_norm"] = peak[1] / i_max
            peak_dict["i_tic_norm"] = peak[1] / i_sum
            peak_dict["mz"] = peak[0]
            peak_dict["mz_nl"] = float(spectrum["Precursor_MZ"]) - peak[0]
            peak_dict["scan"] = spectrum["spectrum_id"]
            peak_dict["precmz"] = float(spectrum["Precursor_MZ"])

            ms2mz_list.append(peak_dict)
        
        # Turning into pandas data frames
        if len(ms2mz_list) > 0:
            ms2_df = pd.DataFrame(ms2mz_list)
            ms2_df_list.append(ms2_df)
            
    # Merging
    ms2_df = pd.concat(ms2_df_list).reset_index()

    return ms2_df