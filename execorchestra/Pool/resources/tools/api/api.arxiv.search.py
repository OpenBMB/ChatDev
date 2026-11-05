from _apilib import get, a
get("http://export.arxiv.org/api/query","arxiv",params={"search_query":f"all:{a(1)}","max_results":a(2,"3")})
