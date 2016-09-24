import bct
import igraph
from itertools import combinations 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pprint import pprint
import seaborn as sns
from sklearn.metrics.cluster import normalized_mutual_info_score

#work around for spyder bug in python 3
import warnings
warnings.simplefilter(action = "ignore", category = RuntimeWarning)

# Utilities
def calc_small_world(G):
    # simulate random graphs with same number of nodes and edges
    sim_out = simulate(rep = 10000, fun = lambda: gen_random_graph(n = len(G.vs), m = len(G.es)))
    # get average C and L for random
    C_random = np.mean([i[1] for i in sim_out])
    L_random = np.mean([i[2] for i in sim_out])
    # calculate relative clustering and path length vs random networks
    Gamma = G.transitivity_undirected()/C_random
    Lambda = G.average_path_length()/L_random
    # small world coefficient
    Sigma = Gamma/Lambda
    return (Sigma, Gamma, Lambda)

def gen_random_graph(n = 10, m = 10, template_graph = None):
    if template_graph:
        G = template_graph.copy()
        G.rewire() # bct.randomizer_bin_und works on binary adjrices
    else:
        #  Generates a random binary graph with n vertices and m edges
        G = igraph.Graph.Erdos_Renyi(n = n, m = m)    
    # get cluster coeffcient. Transitivity is closed triangles/total triplets
    c = G.transitivity_undirected() 
    # get average (shortest) path length
    l = G.average_path_length()
    return (G,c,l,c/l)

def graph_to_matrix(G):
    if 'weight' in G.es.attribute_names():
        graph_mat = np.array(G.get_adjacency(attribute = 'weight').data)
    else:
        graph_mat = np.array(G.get_adjacency().data)
    return graph_mat
    
def pairwise_MI(data):
    columns = data.columns
    MI_df = pd.DataFrame(index = columns, columns = columns)
    for c1,c2 in combinations(columns, 2):
        cleaned = data[[c1,c2]].dropna()
        MI = normalized_mutual_info_score(cleaned[c1], cleaned[c2])
        MI_df.loc[c1,c2] = MI
        MI_df.loc[c2,c1] = MI
    return MI_df.astype(float)
    
def simulate(rep = 1000, fun = lambda: gen_random_graph(100,100)):
    output = []
    for _ in range(rep):
        output.append(fun())
    return output
          
    
def threshold_proportional_sign(W, threshold):
    sign = np.sign(W)
    thresh_W = bct.threshold_proportional(np.abs(W), threshold)
    W = thresh_W * sign
    return W
    
# Visualization
    
def get_visual_style(G,  layout = 'kk', vertex_size = None, size = 1000, labels = None, avg_num_edges = 5):
    """
    Creates an appropriate visual style for a graph. 
    
    Parameters
    ----------
    G: igraph object
        graph that the visual style will be based on
    layout: igraph.layout or str ('kk', 'circle', 'grid' or other igraph layouts), optional
        Determines how the graph is displayed. If a string is provided, assume it is
        a specification of a type of igraph layout using the graph provided. If an
        igraph.layout is provided it must conform to the number of vertices of the graph
    vertex_size: str, optional
        if defined, uses this graph metric to determine vertex size
    size: int, optinal
        determines overall size of graph display. Other sizes (vertex size, font size)
        are proportional to this value. Figures are always square
    labels: list the size of the number of vertices, optional
        Used to label vertices. Numbers are used if no labels are provided
    avg_num_edges: int > 1
        thresholds the edges on the graph so each node has, on average, avg_num_edges
        
    Returns
    ----------
    visual_style: dict
        the dictionary of attribute values to be used by igraph.plot
    """
    # make layout:
    if type(layout) == igraph.layout.Layout:
        graph_layout = layout
    elif type(layout) == str:
        graph_layout = G.layout(layout)
        
    # color by community and within-module-centrality
    # each community is a different color palette, darks colors are more central to the module
    if 'community' in G.vs.attribute_names():
        community_count = np.max(G.vs['community'])
        if community_count <= 6 and 'subgraph_eigen_centrality' in G.vs.attribute_names():
            num_colors = 20.0
            palettes = ['Blues','Reds','Greens','Greys','Purples','Oranges']
            
            min_degree = np.min(G.vs['within_module_degree'])
            max_degree = np.max(G.vs['within_module_degree']-min_degree)
            within_degree = [(v-min_degree)/max_degree for v in G.vs['within_module_degree']]
            within_degree = np.digitize(within_degree, bins = np.arange(0,1,1/num_colors))
            
            vertex_color = [sns.color_palette(palettes[v['community']-1], int(num_colors)+1)[within_degree[i]] for i,v in enumerate(G.vs)]
        else:
            palette = sns.cubehelix_palette(community_count)
            vertex_color = [palette[v['community']-1] for v in G.vs]
    else:
        vertex_color = 'red'
    
    visual_style = {'layout': graph_layout, 
                    'vertex_color': vertex_color, 
                    'vertex_label_size': size/130.0,
                    'bbox': (size,size),
                    'margin': size/20.0}
    if 'weight' in G.es.attribute_names():
        proportion = max(0,min([100,100-(avg_num_edges*len(G.vs))/len(G.es)*100]))
        edge_threshold = np.percentile(np.abs(G.es['weight']),proportion)
        visual_style['edge_width'] = [abs(w)**1.4*size/230.0 if abs(w) > edge_threshold else 0 for w in G.es['weight']]
        if np.sum([e<0 for e in G.es['weight']]) > 0:
            visual_style['edge_color'] = [['#3399FF','#202020','#FF6666'][int(np.sign(w)+1)] for w in G.es['weight']]
        else:
            visual_style['edge_color'] = '#202020'
    if vertex_size:
        visual_style['vertex_size'] = [c*(size/40.0)+(size/80.0) for c in G.vs[vertex_size]]
    if labels:
        visual_style['vertex_label'] = labels
    elif 'id' in G.vs.attribute_names():
        visual_style['vertex_label'] = G.vs['id']
    else:
        visual_style['vertex_label'] = range(len(G.vs))
    
    return visual_style
    
def plot_graph(G, visual_style = None, **kwargs):
    if not visual_style:
        visual_style = get_visual_style(G)
    visual_style.update(**kwargs)
    fig = igraph.plot(G, **visual_style)
    return fig

def plot_mat(mat, labels = []):
    fig = plt.figure(figsize = [16,12])
    ax = fig.add_axes([.25,.15,.7,.7]) 
    sns.heatmap(mat)
    if len(labels) > 0:
        ax.set_yticklabels(labels, rotation = 0, fontsize = 'large')
    return fig
    
def print_community_members(G, lookup = {}, file = None):
    assert set(['community','id','within_module_degree','name',  'eigen_centrality']) <=  set(G.vs.attribute_names()), \
        "Missing some required vertex attributes. Vertices must have id, name, part_coef, eigen_centrality, community and within_module_degree"
        
    if file:
        f = open(file,'a')
    else:
        f = None
        
    print('Key: Node index, Within Module Degree, Measure, Eigenvector centrality', file = f)
    for community in np.unique(G.vs['community']):
        #find members
        members = [lookup.get(v['name'],v['name']) for v in G.vs if v['community'] == community]
        # ids and total degree
        ids = [v['id'] for v in G.vs if v['community'] == community]
        eigen = ["{0:.2f}".format(v['eigen_centrality']) for v in G.vs if v['community'] == community]
        #sort by within degree
        within_degrees = ["{0:.2f}".format(v['within_module_degree']) for v in G.vs if v['community'] == community]
        to_print = list(zip(ids, within_degrees,  members, eigen))
        to_print.sort(key = lambda x: -float(x[1]))
        
        print('Members of community ' + str(community) + ':', file = f)
        pprint(to_print, stream = f)
        print('', file = f)
        
# community functions
def community_reorder(G):
    assert set(['community']) <=  set(G.vs.attribute_names()), \
        'Graph must have "community" and "id" as a vertex attributes'
    community = G.vs['community']
    reorder_index = np.argsort(community)
    # hold graph attributes:
    attribute_names = G.vs.attributes()
    attribute_values = [G.vs[a] for a in attribute_names]
    attribute_df = pd.DataFrame(attribute_values, index = attribute_names).T
    sorted_df = attribute_df.reindex(reorder_index).reset_index()
    
    # rearrange connectivity matrix
    graph_mat = graph_to_matrix(G)
    graph_mat = graph_mat[:,reorder_index][reorder_index]

    # make a binary version if not weighted
    if 'weight' in G.es.attribute_names():
        G = igraph.Graph.Weighted_Adjacency(graph_mat.tolist(), mode = 'undirected')
    else:
        G = igraph.Graph.Adjacency(graph_mat.tolist(), mode = 'undirected')
    for name in attribute_names:
        G.vs[name] = sorted_df[name]
    
    return G
        
            
def get_subgraph(G, community = 1):
    assert set(['community']) <=  set(G.vs.attribute_names()), \
        'Graph must have "community" and "id" as a vertex attributes'
    subgraph = G.induced_subgraph([v for v in G.vs if v['community'] == community])
    subgraph.vs['community'] = subgraph.vs['subgraph_community']
    subgraph.vs['eigen_centrality'] = subgraph.vs['subgraph_eigen_centrality']
    del subgraph.vs['subgraph_community']
    del subgraph.vs['subgraph_eigen_centrality']
    return subgraph
      
def subgraph_analysis(G, community_alg = None):
    assert set(['community','id']) <=  set(G.vs.attribute_names()), \
        'Graph must have "community" and "id" as a vertex attributes'
    for c in np.unique(G.vs['community']):
        subgraph = G.induced_subgraph([v for v in G.vs if v['community'] == c])
        subgraph_mat = graph_to_matrix(subgraph)
        if 'weight' in G.es.attribute_names():
            subgraph.vs['eigen_centrality'] = subgraph.eigenvector_centrality(directed = False, weights = subgraph.es['weight'])
        else:
            subgraph.vs['eigen_centrality'] = subgraph.eigenvector_centrality(directed = False)
        G.vs.select(lambda v: v['id'] in subgraph.vs['id'])['subgraph_eigen_centrality'] = subgraph.vs['eigen_centrality']
        if community_alg:
            comm, Q = community_alg(subgraph_mat)
            subgraph.vs['community'] = comm
            G.vs.select(lambda v: v['id'] in subgraph.vs['id'])['subgraph_community'] = subgraph.vs['community']
            
# Main graph analysis function
def Graph_Analysis(data, thresh_func = bct.threshold_proportional, community_alg = bct.community_louvain, 
                   edge_metric = 'pearson', threshold = .15, weight = True, reorder = True, 
                   display = True, layout = 'kk', avg_num_edges = 5, print_options = {}, plot_options = {}):
    """
    Creates and displays graphs of a data matrix.
    
    Parameters
    ----------
    data: pandas DataFrame
        data to use to create the graph
    thresh_func: function that takes in a connectivity matrix and thresholds
        any algorithm that returns a connectivity matrix of the same size as the original may be used.
        intended to be used with bct.threshold_proportional or bct.threshold_absolute
    community_alg: function that takes in a connectivity matrix and returns community assignment
        intended to use algorithms from brain connectivity toolbox like commnity_louvain or 
        modularity_und. Must return a list of community assignments followed by Q, the modularity
        index
    edge_metric: str: 'pearson', 'separman' or 'MI'
        relationship metric between nodes. MI stands for mutual information. "abs_"
        may be used in front of "pearson" or "spearman" to get the absolute value
        of the correlations, e.g. abs_pearson
    threshold: float 0 <= x <= 1, optional
        the proportion of weights to keep (to be passed to bct.threshold_proportion)
    weight: bool, optional
        if True, creates a weighted graph (vs. a binary)
    reorder: bool, optional
        if True, reorder vertices based on community assignment
    display: bool, optinal
        if True, display the graph and print node membership
    layout: str: 'kk', 'circle', 'grid' or other igraph layouts, optional
        Determines how the graph is displayed
    avg_num_edges: int > 1
        thresholds the edges on the graph so each node has, on average, avg_num_edges
    print_options: dict, optional
        dictionary of arguments to be passed to print_community_members
    plot_options: dict, optional
        dictionary of arguments to be passed to plot_graph
        
    Returns
    ----------
    G: igraph Graph
        the graph object created by the function
    graph_mat: numpy matrix
        the matrix used to create the graph
    """
    assert edge_metric in ['pearson','spearman','MI','abs_pearson','abs_spearman'], \
        'Invalid edge metric passed. Must use "pearson", "spearman", or "MI"'
    if edge_metric == 'MI':
        connectivity_matrix = pairwise_MI(data).as_matrix()
    else:
        *qualifier, edge_metric = edge_metric.split('_')
        if (qualifier or [None])[0] == 'abs':
            connectivity_matrix = abs(data.corr(method = edge_metric)).as_matrix()
        else:
            connectivity_matrix = data.corr(method = edge_metric).as_matrix()
            
    #threshold and remove diagonal
    graph_mat = thresh_func(connectivity_matrix,threshold)
    
    # make a binary version if not weighted
    if not weight:
        graph_mat = np.ceil(graph_mat)
        G = igraph.Graph.Adjacency(graph_mat.tolist(), mode = 'undirected')
    else:
        G = igraph.Graph.Weighted_Adjacency(graph_mat.tolist(), mode = 'undirected')
    column_names = data.columns
    # community detection
    # using louvain but also bct.modularity_und which is "Newman's spectral community detection"
    # bct.modularity_louvain_und_sign
    comm, mod = community_alg(graph_mat)
    G.vs['community'] = comm
    G.vs['id'] = range(len(G.vs))
    G.vs['name'] = column_names
    G.vs['within_module_degree'] = bct.module_degree_zscore(graph_mat,comm)
    G.vs['part_coef'] = bct.participation_coef(graph_mat, comm)
    
    if weight:
        G.vs['eigen_centrality'] = G.eigenvector_centrality(directed = False, weights = G.es['weight'])
    else:
        G.vs['eigen_centrality'] = G.eigenvector_centrality(directed = False)
        
    #if reorder, reorder vertices by community membership
    if reorder:
        G = community_reorder(G)
        
    # calculate subgraph (within-community) characteristics
    subgraph_analysis(G, community_alg = community_alg)
    
    # visualize
    visual_style = {}
    visual_style = get_visual_style(G, layout = layout, vertex_size = 'eigen_centrality', size = 6000, avg_num_edges = avg_num_edges)
    if display:
        # plot community structure
        print_community_members(G, **print_options)
        plot_graph(G, visual_style = visual_style, **plot_options)
    return (G, graph_mat, visual_style)