set -e
for model in adaptive_n_back_base.model attention_network_task_flanker_base.model attention_network_task_cue_condition.model attention_network_task_flanker_condition.model choice_reaction_time_base.model directed_forgetting_base.model directed_forgetting_condition.model dot_pattern_expectancy_base.model dot_pattern_expectancy_condition.model local_global_letter_base.model local_global_letter_conflict_condition.model local_global_letter_switch_condition.model motor_selective_stop_signal_base.model recent_probes_base.model recent_probes_condition.model shape_matching_base.model shape_matching_condition.model simon_base.model simon_condition.model stop_signal_base.model stroop_base.model stroop_condition.model threebytwo_base.model threebytwo_cue_condition.model threebytwo_task_condition.model
do
sed "s/{MODEL}/$model/g" calculate_hddm_fitstat_retest.batch | sbatch -p russpold
done
