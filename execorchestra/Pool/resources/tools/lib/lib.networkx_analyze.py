from _liblib import ok,err,a
import networkx as nx,json
try:
    G=nx.Graph(); G.add_edges_from(json.loads(a(1))); met=a(2,"degree")
    r=dict(nx.degree_centrality(G)) if met=="degree" else dict(nx.betweenness_centrality(G))
    ok("lib.networkx_analyze",metric=met,nodes=G.number_of_nodes(),edges=G.number_of_edges(),result=r)
except Exception as ex: err("lib.networkx_analyze",str(ex))
