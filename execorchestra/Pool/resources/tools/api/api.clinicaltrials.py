from _apilib import get, a
get("https://clinicaltrials.gov/api/v2/studies","clinicaltrials",params={"query.term":a(1),"pageSize":"3"})
