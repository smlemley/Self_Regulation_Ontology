# imports
from dimensional_structure.utils import (
        create_factor_tree, distcorr,  find_optimal_components, 
        get_scores_from_subset, hierarchical_cluster, quantify_lower_nesting
        )
import glob
from os import makedirs, path
import pandas as pd
from pathos.multiprocessing import ProcessingPool as Pool
import numpy as np
import pickle
import random
from scipy.stats import entropy
from selfregulation.utils.utils import get_behav_data
from selfregulation.utils.r_to_py_utils import get_Rpsych, psychFA
from sklearn.preprocessing import scale

# load the psych R package
psych = get_Rpsych()

# ****************************************************************************
# Peform factor analysis
# ****************************************************************************
# test if sample is suitable for factor analysis

class EFA_Analysis:
    def __init__(self, data, data_no_impute=None):
        self.results = {}
        self.data = data
        if data_no_impute is not None:
            self.data_no_impute = data_no_impute
        # global variables to hold certain aspects of the analysis
        self.max_factors = 0
        
    def adequacy_test(self, verbose=False):
        data = self.data
        # KMO test should be > .6
        KMO_MSA = psych.KMO(data.corr())[0][0]
        # barlett test should be significant
        Barlett_p = psych.cortest_bartlett(data.corr(), data.shape[0])[1][0]
        adequate = KMO_MSA>.6 and Barlett_p < .05
        if verbose:
            print('Is the data adequate for factor analysis? %s' % \
                  ['No', 'Yes'][adequate])
        return adequate, {'Barlett_p': Barlett_p, 'KMO': KMO_MSA}
    
    def get_dimensionality(self, metrics=None, verbose=False):
        if metrics is None:
            metrics = ['BIC', 'parallel']
        if 'BIC' in metrics:
            BIC_c, BICs = find_optimal_components(self.data, metric='BIC')
            self.results['c_metric-BIC'] = BIC_c
            self.results['cscores_metric-BIC'] = BICs
        if 'parallel' in metrics:
            # parallel analysis
            parallel_out = psych.fa_parallel(self.data, fa='fa', fm='ml',
                                             plot=False, **{'n.iter': 100})
            parallel_c = parallel_out[parallel_out.names.index('nfact')][0]
            self.results['c_metric-parallel'] = int(parallel_c)
        if 'SABIC' in metrics:
            # using SABIC
            SABIC_c, SABICs = find_optimal_components(self.data, metric='SABIC')
            self.results['c_metric-SABIC'] = SABIC_c
            self.results['cscores_metric-SABIC'] = SABICs
        if 'CV' in metrics:
            try:
                 # using CV
                CV_c, CVs = find_optimal_components(self.data_no_impute, 
                                                    maxc=50, metric='CV')
                self.results['c_metric-CV'] = CV_c
                self.results['cscores_metric-CV'] = CVs
            except AttributeError:
                print("CV dimensionality could not be calculated. " + \
                      "data_no_impute not found.")
        # record max_factors
        best_cs = {k:v for k,v in self.results.items() if 'c_metric-' in k}
        metric_cs = best_cs.values()
        self.max_factors = int(max(metric_cs))+5
        if verbose:
                print('Best Components: ', best_cs)
    
    def get_metric_cs(self):
        metric_cs = {k:v for k,v in self.results.items() if 'c_metric-' in k}
        return metric_cs
    
    def get_loading_entropy(self, c):
        assert c>1
        loadings = self.results['factor_tree'][c]
        # calculate entropy of each variable
        loading_entropy = abs(loadings).apply(entropy, 1)
        max_entropy = entropy([1/loadings.shape[1]]*loadings.shape[1])
        return loading_entropy/max_entropy
    
    def get_null_loading_entropy(self, c, reps=50):
        assert c>1
        # get absolute loading
        loadings = abs(self.results['factor_tree'][c])
        max_entropy = entropy([1/loadings.shape[1]]*loadings.shape[1])
        permuted_entropies = np.array([])
        for _ in range(reps):
            # shuffle matrix
            for i, col in enumerate(loadings.values.T):
                shuffle_vec = np.random.permutation(col)
                loadings.iloc[:, i] = shuffle_vec
            # calculate entropy of each variable
            loading_entropy = loadings.apply(entropy, 1)
            permuted_entropies = np.append(permuted_entropies,
                                           (loading_entropy/max_entropy).values)
        return permuted_entropies
    
    def run(self, rerun=False, verbose=False):
        # check adequacy
        adequate, adequacy_stats = self.adequacy_test(verbose)
        assert adequate, "Data is not adequate for EFA!"
        self.results['EFA_adequacy'] = {'adequate': adequate, 
                                            'adequacy_stats': adequacy_stats}
        
        # get optimal dimensionality
        if 'c_metric-parallel' not in self.results.keys() or rerun==True:
            if verbose: print('Determining Optimal Dimensionality')
            self.get_dimensionality(verbose=verbose)
            
        # create factor tree
        if verbose: print('Creating Factor Tree')
        run_FA = self.results.get('factor_tree', [])
        if len(run_FA) < self.max_factors or rerun == True:
            ftree, ftree_rout = create_factor_tree(self.data,
                                                   (1,self.max_factors))
            self.results['factor_tree'] = ftree
            self.results['factor_tree_Rout'] = ftree_rout
            
        # quantify lower nesting
        self.results['lower_nesting'] = quantify_lower_nesting(self.results['factor_tree'])
        
        # calculate entropy for each measure at different c's
        entropies = {}
        null_entropies = {}
        for c in range(self.max_factors):
            if c > 1:
                entropies[c] = self.get_loading_entropy(c)
                null_entropies[c] = self.get_null_loading_entropy(c)
        self.results['entropies'] = pd.DataFrame(entropies)
        self.results['null_entropies'] = pd.DataFrame(null_entropies)

    def get_task_representations(self, tasks, c):
        """Take a list of tasks and reconstructs factor scores"""
        def get_attr(fa, attr):
            try:
                index = list(fa.names).index(attr)
                val = list(fa.items())[index][1]
                if len(val) == 1:
                    val = val[0]
                return np.matrix(val)
            except ValueError:
                print('Did not pass a valid attribute')
            
        fa_output = self.results['factor_tree_Rout'][c]
        output = {'weights': get_attr(fa_output, 'weights'),
                  'scores': get_attr(fa_output, 'scores')}
        subset_scores, r2_scores = get_scores_from_subset(self.data,
                                                          output,
                                                          tasks)
        return subset_scores, r2_scores
        
    def get_nesting_matrix(self, explained_threshold=.5):
        factor_tree = self.results['factor_tree']
        explained_scores = -np.ones((len(factor_tree), len(factor_tree)-1))
        sum_explained = np.zeros((len(factor_tree), len(factor_tree)-1))
        for key in self.results['lower_nesting'].keys():
            r =self.results['lower_nesting'][key]
            adequately_explained = r['scores'] > explained_threshold
            explained_score = np.mean(r['scores'][adequately_explained])
            if np.isnan(explained_score): explained_score = 0
            explained_scores[key[1]-1, key[0]-1] = explained_score
            sum_explained[key[1]-1, key[0]-1] = (np.sum(adequately_explained/key[0]))
        return explained_scores, sum_explained
    
    def verify_factor_solution(self):
        fa, output = psychFA(self.data, 10)
        scores = output['scores'] # factor scores per subjects derived from psychFA
        scaled_data = scale(self.data)
        redone_scores = scaled_data.dot(output['weights'])
        redone_score_diff = np.mean(scores-redone_scores)
        assert(redone_score_diff < 1e-5)

class HCA_Analysis():
    """ Runs Hierarchical Clustering Analysis """
    def __init__(self, dist_metric):
        self.results = {}
        self.dist_metric = dist_metric
        self.metric_name = 'unknown'
        if self.dist_metric == distcorr:
            self.metric_name = 'distcorr'
        else:
            self.metric_name = self.dist_metric
        
    def cluster_data(self, data):
        output = hierarchical_cluster(data.T, 
                                      pdist_kws={'metric': self.dist_metric})
        self.results['clustering_metric-%s_input-data' % self.metric_name] = output
        
    def cluster_EFA(self, EFA, c):
        loadings = EFA.results['factor_tree'][c]
        output = hierarchical_cluster(loadings, 
                                      pdist_kws={'metric': self.dist_metric})
        self.results['clustering_metric-%s_input-EFA%s' % (self.metric_name, c)] = output

    def run(self, data, EFA, rerun=True, verbose=False):
        if ('clustering_metric-%s_input-data' % self.metric_name in 
            self.results.keys()) or (rerun==True):
            if verbose: print("Clustering data")
            self.cluster_data(data)
        if verbose: print("Clustering EFA")
        for c in EFA.get_metric_cs().values():
            self.cluster_EFA(EFA, c)

class Results(EFA_Analysis, HCA_Analysis):
    """ Class to hold olutput of EFA, HCA and graph analyses """
    def __init__(self, datafile, dist_metric=distcorr):
        """
        Args:
            dist_metric: distance metric for hierarchical clustering that is 
            passed to pdist
        """
        # load data
        imputed_data = get_behav_data(dataset=datafile, file='meaningful_variables_imputed.csv')
        cleaned_data = get_behav_data(dataset=datafile, file='meaningful_variables_clean.csv')
        self.data = imputed_data
        self.data_no_impute = cleaned_data
        # set up plotting files
        self.plot_file = path.join('Plots', datafile)
        self.output_file = path.join('Output', datafile)
        makedirs(self.plot_file, exist_ok = True)
        makedirs(self.output_file, exist_ok = True)
        # set vars
        self.dist_metric = dist_metric
        
        # initialize analysis classes
        self.EFA = EFA_Analysis(self.data, self.data_no_impute)
        self.HCA = HCA_Analysis(dist_metric=self.dist_metric)
        
    def run_EFA_analysis(self, rerun=False, verbose=False):
        if verbose:
            print('*'*79)
            print('Running EFA')
            print('*'*79)
        self.EFA.run(rerun=rerun, verbose=verbose)

    def run_HCA_analysis(self, verbose=False):
        if verbose:
            print('*'*79)
            print('Running HCA')
            print('*'*79)
        self.HCA.run(self.data, self.EFA, verbose=verbose)
    
    # Bootstrap Functions
    def gen_resample_data(self):
        return self.data.sample(self.data.shape[0], replace=True)
    
    def run_EFA_bootstrap(self, boot_data=None, verbose=False):
        if boot_data is None:
            boot_data = self.gen_resample_data()
        EFA_boot = EFA_Analysis(boot_data)
        EFA_boot.run(verbose=verbose)
        return EFA_boot
    
    def run_HCA_bootstrap(self, EFA, boot_data=None, verbose=False):
        if boot_data is None:
            boot_data = self.gen_resample_data()
        HCA_boot = HCA_Analysis(self.dist_metric)
        HCA_boot.run(boot_data, EFA, verbose=verbose)
        return HCA_boot

    def run_bootstrap(self, run_HCA=True, verbose=False, save_dir=None):
        boot_data = self.gen_resample_data()
        EFA_boot = self.run_EFA_bootstrap(boot_data, verbose)
        boot_run = {'data': boot_data, 'EFA': EFA_boot}
        if run_HCA:
            HCA_boot = self.run_HCA_bootstrap(EFA_boot, boot_data, verbose)
            boot_run['HCA'] = HCA_boot
        if save_dir is not None:
            ID = random.getrandbits(16)
            filename = 'bootstrap_ID-%s.pkl' % ID
            pickle.dump(boot_run, 
                        open(path.join(save_dir, filename),'wb'))
        else:
            return boot_run
    
    def run_parallel_boot(self, reps, save_dir, run_HCA=True):
        def bootstrap_wrapper(ignored):
            self.run_bootstrap(save_dir=save_dir, run_HCA=run_HCA)
        pool = Pool()
        pool.map(bootstrap_wrapper, range(reps))
        pool.close()
        pool.join()
        
    def reduce_boot(self, boot_run):
        EFA = boot_run['EFA']
        HCA = boot_run['HCA']
        cs = EFA.get_metric_cs()
        factors = {i: EFA.results['factor_tree'][i] for i in cs.values()}
        results = {}
        results['metric_cs'] = cs
        results['factor_solutions'] = factors
        results['HCA_solutions'] = HCA.results
        return results
        
    def reduce_boot_files(self, boot_loc, save=False):
        """ Run "run_boostrap", but only save important params """
        results = []
        for filey in glob.glob(path.join(boot_loc, 'bootstrap*ID*')):
            boot_run = pickle.load(open(filey, 'rb'))
            results.append(self.reduce_boot(boot_run))
        if save == True:
            pickle.save(open(path.join(boot_loc, 'bootstrap_aggregate.pkl', 'wb')))
        else:
            return results
    

                


    
    
    