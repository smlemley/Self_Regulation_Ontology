docker run --rm  -ti sro_dataprep


# calculate exp dvs
data_loc=/home/ian/tmp/
output=/media/Data/Ian/Experiments/expfactory/Self_Regulation_Ontology/batch_files/singularity_scripts/output
docker run --rm  \
--mount type=bind,src=$data_loc,dst=/Data \
--mount type=bind,src=$output,dst=/output \
-ti sro_dataprep batch_files/calculate_exp_DVs.py stim_selective_stop_signal mturk_complete --out_dir /output 

# save data
data_loc=/home/ian/tmp
output=/home/ian/tmp
docker run --rm  \
--mount type=bind,src=$data_loc,dst=/Data \
--mount type=bind,src=$output,dst=/SRO/Data \
-ti sro_dataprep python data_preparation/mturk_save_data.py
