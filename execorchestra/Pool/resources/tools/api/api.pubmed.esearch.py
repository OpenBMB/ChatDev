from _apilib import get, a
get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi","pubmed",params={"db":"pubmed","term":a(1),"retmode":"json","retmax":"5"})
