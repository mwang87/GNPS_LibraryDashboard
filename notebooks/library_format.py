import json
import sys
import pandas as pd

input_json_filename = sys.argv[1]
output_filename = sys.argv[2]

spectra_list = json.loads(open(input_json_filename).read())

output_list = []
for spectra in spectra_list:
    output_dict = {}

    smiles = spectra["Smiles"]

    if len(smiles) > 5:
        output_dict["smiles"] = smiles
        output_dict["library"] = spectra["library_membership"]
        output_dict["Compound_Name"] = spectra["Compound_Name"]

        output_list.append(output_dict)

output_df = pd.DataFrame(output_list)
output_df.to_csv(output_filename, index=False, sep="\t")