import sqlite3
import subprocess
from collections import defaultdict

from bs4 import BeautifulSoup
import urllib.parse
import json
import html2text
import sys
import subprocess
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")


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


def get_url_page(url, chunk_num=0, dbg=False):
    page_length = 1000
    page_overlap = 200

    h = html2text.HTML2Text()
    h.ignore_links = False
    html = subprocess.check_output(['curl', url]).decode("utf-8")
    if dbg:
        print(f"Full HTML: {len(encoder.encode(html))} tokens")

    text = h.handle(html)
    lines = text.split("\n")
    page = ""
    next_page = ""
    pages = list()
    for l in lines:
        upp = page + "\n" + l
        if len(encoder.encode(upp)) > page_length - page_overlap:
            next_page += l
        if len(encoder.encode(upp)) > page_length:
            pages.append(page)
            page = next_page
            next_page = ""
        else:
            page = upp
    if len(next_page) > 0:
        pages.append(next_page)
    if dbg:
        for p in pages:
            print(len(encoder.encode(p)), len(p.split("\n")))
        if len(pages)>1:
            print(pages[-2][-1000:])
            print("-----------------------")
            print(pages[-1][:1000])
    return {
        'page_content': pages[chunk_num],
        'total_pages': len(pages)
    }

get_url_page.openai_desc = {
    "name": "get_url_page",
    "description": "After a call to this function, you MUST call the search_status_update function. Slices the given URL into chunks (about 1500 words) and returns the requested chunk number. It returns the result of the requested chunk and also the total number of chunks available at that URL.  ",
    "parameters": {
        "type": "object",
        "properties": {
          "url": {
              "type": "string",
              "description": "URL to consult"
          },
            "chunk_num": {
                "type": "integer",
                "description": "number of the chunk to return. Defaults to zero,"
            }
        },
        "required": ["url"]
    }
}

search_status=status = defaultdict(list)
def search_status_update(url, chunk, status):
    search_status[url].append((chunk,status))

    return dict(search_status)

search_status_update.openai_desc = {
    "name": "search_status_update",
    "description": "Keeps in memory the presence or absence of relevant information on the URL at the given chunk.",
    "parameters": {
        "type": "object",
        "properties": {
          "url": {
              "type": "string",
              "description": "URL that was consulted"
          },
            "chunk": {
                "type": "integer",
                "description": "Chunk number that was consulted,"
          },
            "status": {
                "type": "string",
                "description": "Was the information you search present on this chunk?",
                "enum": ["yes", "no", "partially"]
          }
        },
        "required": ["url", "chunk", "status"]
    }
}

sql_file = "playground/playground.db"
def sql_request(request):
    result = []
    conn = sqlite3.connect(sql_file)
    try:
        c = conn.cursor()
        result = []
        if request.strip() != "":
            c.execute(request)
            conn.commit()
            result = c.fetchall()
    except sqlite3.Error as e:
        result = f"{type(e).__name__}: {e}"
    except Exception as e:
        result = f"{type(e).__name__}: {e}"
    finally:
        conn.close()
    return result
sql_request.openai_desc = {
    "name": "sql_request",
    "description": "Executes a SQL request on a local sqlite file.",
    "parameters": {
        "type": "object",
        "properties": {
          "request": {
              "type": "string",
              "description": "SQL request"
          }
        },
        "required": ["request"]
    }
}

def flask_creation_py(python_code):
    try:
        f = open("playground/app.py", "w")
        f.write(python_code)
        f.close()
        return "OK"
    except Exception as e:
        return f"{type(e).__name__}: {e}"
flask_creation_py.openai_desc = {
    "name": "flask_creation_py",
    "description": f"Creates a app.py python file run it as a flask application. The application can access the local sqlite database named playground.db. Remember that JSON does not support multilines string. All line returns must be escaped.",
    "parameters": {
        "type": "object",
        "properties": {
            "python_code": {
                "type": "string",
                "description": "content of the python file to write as app.py."
            },
        },
        "required": ["python_code"]
    }
}

def flask_creation_html(html_template, file_name):
    try:
        f = open(f"playground/templates/{file_name}", "w")
        f.write(html_template)
        f.close()
        return "OK"
    except Exception as e:
        return f"{type(e).__name__}: {e}"

flask_creation_html.openai_desc = {
    "name": "flask_creation_html",
    "description": f"Creates a HTML template for the flask application.",
    "parameters": {
        "type": "object",
        "properties": {
            "html_template":{
                "type": "string",
                "description": "Content of the template."
            },
            "file_name": {
                "type": "string",
                "description": "Name of the template. It will be stored in templates/"
            }
        },
        "required": ["html_template","file_name"]
    }
}
