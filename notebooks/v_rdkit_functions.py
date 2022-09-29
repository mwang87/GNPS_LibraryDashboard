import pandas
import rdkit
from rdkit import Chem
from rdkit.Chem import Draw

# identifies molecules described in input library based on known SMILES in metadata
def mol_from_smiles_in_library(library_df):
    
    input_library = library_df
    
    # identifies all SMILES in library dataframe
    smiles_list = input_library[input_library['Smiles'].notnull()]['Smiles'].unique()
    
    # matches SMILES with rdkit molecular object while excluding dataframe rows that do not contain valid SMILES
    smiles_w_rdkit_obj_dict = { AZsmiles : Chem.MolFromSmiles(AZsmiles) for AZsmiles in smiles_list if Chem.MolFromSmiles(AZsmiles) != None }
    
    return smiles_w_rdkit_obj_dict


# returns a subselection of library dataframe for rows containing substructure of interest
def substruct_search_from_smiles(library_df, smiles_w_rdkit_obj_dict, substruct_search):
    
    input_library = library_df
    
    smiles_w_rdkit_obj = smiles_w_rdkit_obj_dict
    
    substruct_search = substruct_search
    
    # user input: substructure search as SMILES as string
    substructure_filter = Chem.MolFromSmiles(substruct_search)
    
    # identify rows that contain substructure
    matched_list = [k for k,v in smiles_w_rdkit_obj_dict.items() if v.HasSubstructMatch(substructure_filter)]
    
    library_df_w_substruc_matched = input_library[input_library['Smiles'].isin(matched_list)]
    
    return library_df_w_substruc_matched