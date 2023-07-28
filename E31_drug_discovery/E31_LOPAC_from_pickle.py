import sys

sys.path.append("..")
import pandas as pd
from sklearn.preprocessing import StandardScaler
import pickle

################################################################################################
## Test on drug discovery data
#################################################################################################
# load the data and the model
drug_data_tot = pd.read_csv("E31_LOPAC_data.csv", index_col=False)
drug_data_tot = drug_data_tot.drop("Unnamed: 0", axis=1)

clf_svm_2 = pickle.load(open('E31_SVM_model.sav', 'rb'))

# AT this stage, before irrelevant features are deleted, we need to correct the intensity of different plates
# against each other. To start with we will not correct features that will vary by cell density, as later cell no.
# varies as drugs kill off cells, but correction would still be applied.

LOPAC_meta = pd.read_csv("GCGR-Lpc-Metadata.csv")
LOPAC_meta['Barcode'] = LOPAC_meta['Barcode'].str.replace('.', '-')
drug_data_temp = drug_data_tot.copy()

drug_data_temp = drug_data_temp.set_index(["Metadata_platename", "Metadata_well"])
compound = (LOPAC_meta.set_index(['Barcode', "Well Name"])['chemical_name'])

drug_data_temp["compound"] = compound
drug_data_tot["compound"] = list(drug_data_temp["compound"])

del drug_data_temp

DMSO_grouped_means = pd.DataFrame(
    drug_data_tot[drug_data_tot["compound"] == "DMSO"].groupby(["Metadata_platename"]).mean())
# DMSO_grouped_means now contains the mean of DMSO samples in 01 and 02 wells, for each plate
plate_names = list(DMSO_grouped_means.index)

print(DMSO_grouped_means)

# drop columns not needed for ML

drug_data_reduced = drug_data_tot.copy().drop(
    ["Metadata_well", "ImageNumber", "ObjectNumber"], axis=1)

# scale data
# We want to train a scaler based on the DMSO controls of each plate, then apply to all data on that plate
# train scaler on the DMSO controls, then apply to all

# train scaler based on control
scaled_list = []
for plate in set(drug_data_reduced["Metadata_platename"]):
    plate_data = drug_data_reduced.loc[drug_data_reduced["Metadata_platename"] == plate, :]
    scaler = StandardScaler().fit(plate_data[plate_data['compound'] == "DMSO"].drop(['compound', "Metadata_platename"], axis=1))
    plate_data = plate_data.drop(['compound', "Metadata_platename"], axis=1)
    plate_data_scaled = scaler.transform(plate_data)
    plate_data_scaled = pd.DataFrame(plate_data_scaled, index=plate_data.index)
    scaled_list.append(plate_data_scaled)


drug_data_scaled = pd.concat(scaled_list)
# apply the classifier to the drug discovery data
drug_pred = clf_svm_2.predict(drug_data_scaled)
drug_pred_probs = clf_svm_2.decision_function(drug_data_scaled)

drug_data_tot = drug_data_tot[["Metadata_well", "ImageNumber", "ObjectNumber", "compound", "Metadata_platename"]]

# we produce a senescence score for each cell

drug_data_tot["sen_score"] = pd.DataFrame(drug_pred_probs, index = drug_data_scaled.index)

drug_data_tot["sen_prediction"] = pd.DataFrame(drug_pred, index = drug_data_scaled.index)

del drug_data_scaled
del drug_data_reduced

drug_data_tot = drug_data_tot.dropna(axis=1)

# group the data so we know what the senescence score is for each well of each plate

grouped_dat = drug_data_tot.groupby(["Metadata_platename", "Metadata_well"])
# find the mean cell senescence score per well
mean_sen_score = grouped_dat.mean()["sen_score"]
# find the standard deviation in senescence score per well
std_sen_score = grouped_dat.std()["sen_score"]

tot_sen = grouped_dat.sum()["sen_prediction"]

index_sen_score = grouped_dat.mean().index

# px.scatter(y=drug_pred_probs, x=np.arange(len(drug_pred_probs)))

# px.scatter(y=mean_sen_score, error_y=std_sen_score, x=list([x[0] + "_" + x[1] for x in index_sen_score]))

# find the number of cells in each well

cell_no = pd.DataFrame(
    drug_data_tot.groupby(["Metadata_platename", "Metadata_well", "ImageNumber"]).max()["ObjectNumber"].groupby(
        ["Metadata_platename", "Metadata_well"]).sum())

# create summary data for each well and save to file

output_data = pd.DataFrame(mean_sen_score)

output_data["std_sen_score"] = std_sen_score
output_data["cell_no"] = cell_no
output_data["number_sen"] = tot_sen

output_data.to_csv('E31_senscore_LOPAC.csv')
drug_data_tot["ID"] = drug_data_tot["Metadata_platename"] + "_" + drug_data_tot["Metadata_well"]
drug_data_tot.to_csv('E31_LOPAC_full_data.csv')
