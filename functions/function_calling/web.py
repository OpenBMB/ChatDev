import os


def web_search(query: str, page: int = 1, language: str = "en", country: str = "us") -> str:
    """
    Performs a web search based on the user-provided query with pagination.

    Args:
        query (str): The keyword(s) to search for.
        page (int): The page number of the results to return. Defaults to 1.
        language (str): The language of the search results. Defaults to "en", can be "en", "zh-cn", "zh-tw", "ja", "ko".
        country (str): The country of the search results. Defaults to "us", can be "us", "cn", "jp", "kr".

    Returns:
        str: A formatted string containing the title, link, and snippet of the search results for the specified page.
    """
    import requests
    import json

    url = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query,
        "page": page,
        "hl": language,
        "gl": country
    })
    headers = {
        'X-API-KEY': os.getenv("SERPER_DEV_API_KEY"),
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    try:
        data = response.json()
        return __format_serper_results(data)
    except json.JSONDecodeError:
        return response.text


def __format_serper_results(data: dict) -> str:
    """
    Formats the raw JSON response from Serper.dev into a structured string.
    """
    formatted_output = []

    # 1. Knowledge Graph
    if "knowledgeGraph" in data:
        kg = data["knowledgeGraph"]
        formatted_output.append("## Knowledge Graph")
        if "title" in kg:
            formatted_output.append(f"**Title**: {kg['title']}")
        if "type" in kg:
            formatted_output.append(f"**Type**: {kg['type']}")
        if "description" in kg:
            if "descriptionSource" in kg and "descriptionLink" in kg:
                 formatted_output.append(f"**Description**: {kg['description']} (Source: [{kg['descriptionSource']}]({kg['descriptionLink']}))")
            else:
                 formatted_output.append(f"**Description**: {kg['description']}")
        
        if "attributes" in kg:
            formatted_output.append("**Attributes**:")
            for key, value in kg["attributes"].items():
                formatted_output.append(f"- {key}: {value}")
        formatted_output.append("")  # Add spacing

    # 2. Organic Results
    if "organic" in data and data["organic"]:
        formatted_output.append("## Organic Results")
        for i, result in enumerate(data["organic"], 1):
            title = result.get("title", "No Title")
            link = result.get("link", "#")
            snippet = result.get("snippet", "")
            formatted_output.append(f"{i}. **[{title}]({link})**")
            if snippet:
                formatted_output.append(f"   {snippet}")
            
            # Optional: Include attributes if useful, but keep it concise
            if "attributes" in result:
                 for key, value in result["attributes"].items():
                      formatted_output.append(f"   - {key}: {value}")
        formatted_output.append("")

    # 3. People Also Ask
    if "peopleAlsoAsk" in data and data["peopleAlsoAsk"]:
        formatted_output.append("## People Also Ask")
        for item in data["peopleAlsoAsk"]:
            question = item.get("question")
            snippet = item.get("snippet")
            link = item.get("link")
            title = item.get("title")
            
            if question:
                formatted_output.append(f"- **{question}**")
            if snippet:
                formatted_output.append(f"  {snippet}")
            if link and title:
                 formatted_output.append(f"  Source: [{title}]({link})")
        formatted_output.append("")
        
    # 4. Related Searches
    if "relatedSearches" in data and data["relatedSearches"]:
        formatted_output.append("## Related Searches")
        queries = [item["query"] for item in data["relatedSearches"] if "query" in item]
        formatted_output.append(", ".join(queries))

    return "\n".join(formatted_output).strip()


def read_webpage_content(url: str) -> str:
    """
    Reads the content of a webpage and returns it as a string.
    """
    import requests
    import time
    from collections import deque
    import threading

    # Rate limiting configuration
    RATE_LIMIT = 20  # requests
    TIME_WINDOW = 60  # seconds

    # Global state for rate limiting (thread-safe)
    if not hasattr(read_webpage_content, "_request_timestamps"):
        read_webpage_content._request_timestamps = deque()
        read_webpage_content._lock = threading.Lock()

    target_url = f"https://r.jina.ai/{url}"
    key = os.getenv("JINA_API_KEY")

    headers = {}
    if key:
        headers["Authorization"] = key
    else:
        # Apply rate limiting if no key is present
        with read_webpage_content._lock:
            current_time = time.time()
            
            # Remove timestamps older than the time window
            while read_webpage_content._request_timestamps and \
                  current_time - read_webpage_content._request_timestamps[0] > TIME_WINDOW:
                read_webpage_content._request_timestamps.popleft()
            
            # Check if limit reached
            if len(read_webpage_content._request_timestamps) >= RATE_LIMIT:
                # Calculate sleep time
                oldest_request = read_webpage_content._request_timestamps[0]
                sleep_time = TIME_WINDOW - (current_time - oldest_request)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                # After sleeping, we can pop the oldest since it expired (logically)
                # Re-check time/clean just to be safe and accurate, 
                # but effectively we just waited for the slot to free up.
                # Ideally, we add the *new* request time now.
                # Note: after sleep, the current_time has advanced.
                current_time = time.time()
                # Clean up again
                while read_webpage_content._request_timestamps and \
                      current_time - read_webpage_content._request_timestamps[0] > TIME_WINDOW:
                    read_webpage_content._request_timestamps.popleft()

            # Record the execution
            read_webpage_content._request_timestamps.append(time.time())

    response = requests.get(target_url, headers=headers)
    return response.text


if __name__ == "__main__":
    pass
