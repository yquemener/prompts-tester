import subprocess
from bs4 import BeautifulSoup
import urllib.parse
import json


def ddg_search(query, dbg=False):
    # Passes a query to the duckduckgo search engine

    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote_plus(query)
    curl_output = subprocess.check_output(['curl', url])
    soup = BeautifulSoup(curl_output, 'html.parser')
    links = soup.find_all('a', {'class': 'result__url'})

    results = list()

    if links:
        for i in range(5):
            l=links[i].get('href')
            uddg = urllib.parse.parse_qs(urllib.parse.urlparse(l).query)['uddg'][0]
            decoded_url = urllib.parse.unquote(uddg)
            results.append({
                "url": decoded_url
            })
    if dbg:
        print(results)
    return results


ddg_search.openai_desc = {
    "name": "ddg_search",
    "description": "Passes a query to the duckduckgo search engine",
    "parameters": {
        "type": "object",
        "properties": {
          "query": {
              "type": "string",
              "description": "the search terms to be passed to the search engine"
          }
        },
        "required": ["query"]
    }
}