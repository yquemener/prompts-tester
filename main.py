import json
import os
import signal
import sqlite3
import subprocess

from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import configuration as C
from time import sleep


# TODO: Barre de progression "budget tokens"
# TODO: Checkbox à coté des fonctions qui marchent vraiment
# TODO: Arriver à afficher le python/HTML avec les retours à la ligne
# TODO: Statut dynamique ne rechargeant pas la page à chaque fois
# TODO: "Run for X thoughts"
# TODO: Debug de temps en temps le dernier commentaire user est ignoré

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
os.environ["FLASK_ENV"] = "development"
app.debug = True
db = SQLAlchemy(app)
# openai.api_key = open("/home/yves/keys/openAIAPI", "r").read().rstrip("\n")
auth = HTTPBasicAuth()

users = {
    "user": generate_password_hash(C.HTTP_PASSWORD)
}

@app.before_request
def require_auth():
    auth.login_required()

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username


class IgnoreStatusCheckFilter(logging.Filter):
    def filter(self, record):
        return '/playground_status' not in record.getMessage()

logging.getLogger('werkzeug').addFilter(IgnoreStatusCheckFilter())


playground_process = None

def is_port_occupied(port):
    result = subprocess.run(['netstat', '-tuln'], capture_output=True, text=True)
    return str(port) in result.stdout

def is_playground_running():
    global playground_process
    if playground_process is None:
        return False
    return playground_process.poll() is None


# Extract tools information
import tools
documented_functions = {}
openai_functions_arg = []
for item_name in dir(tools):
    item = getattr(tools, item_name)
    if callable(item) and hasattr(item, "openai_desc") and item.__module__ == "tools":
        documented_functions[item_name] = (item, item.openai_desc)
        openai_functions_arg.append(item.openai_desc)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text)
    name = db.Column(db.String(50))

    # New fields
    function_call = db.Column(db.Text)
    arguments = db.Column(db.Text)

    def __repr__(self):
        return '<Message %r>' % self.id


# Does a SQL request, returns result if any
def db_req(dbname, req, args=None, row_factory=False):
    if args is None:
        args = []
    conn = sqlite3.connect(dbname)
    if row_factory:
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    res = cursor.execute(req, args)
    if res:
        res = res.fetchall()
    conn.commit()
    conn.close()
    return res


@app.route("/playground/")
@auth.login_required
def playground():
    tables = db_req(tools.sql_file,
           "SELECT name FROM sqlite_master WHERE type='table';", row_factory=True)
    table_data = {}
    for table in tables:
        table_name = table['name']
        rows=db_req(tools.sql_file, f"SELECT * FROM {table_name};", row_factory=True)
        table_data[table_name] = [dict(row) for row in rows]
    return render_template('playground_db.html', table_data=table_data)

@app.route("/playground/reset", methods=["POST"])
@auth.login_required
def playground_reset():
    tables = db_req(tools.sql_file, f"SELECT name FROM sqlite_master WHERE type='table';")
    for table in tables:
        if table[0].startswith("sqlite_"):
            continue
        table_name = table[0]
        db_req(tools.sql_file, f"DROP TABLE IF EXISTS {table_name};")
    return make_response("", 200)

@app.route("/delete/<int:id>")
@auth.login_required
def delete(id):
    message = Message.query.get_or_404(id)
    db.session.delete(message)
    db.session.commit()
    return redirect(url_for('home'))

@app.route("/delete_all/")
@auth.login_required
def delete_all():
    raise NotImplementedError
    try:
        db.session.query(Message).delete()
        db.session.commit()
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@app.route('/playground_start', methods=['POST'])
@auth.login_required
def start_app_playground():
    global playground_process
    if playground_process is None or playground_process.poll() is not None:
        playground_process = subprocess.Popen(
            ["python", "-m", "gunicorn", "--log-level", "debug", "--reload", "-b", ":5481", "app:app"],
            cwd='./playground/')
    return jsonify(success=True)

@app.route('/playground_stop', methods=['POST'])
@auth.login_required
def stop_app_playground():
    global playground_process

    # Get the process ID that occupies the port
    proc = subprocess.Popen(['lsof', '-t', '-i:5481'], stdout=subprocess.PIPE)
    out, err = proc.communicate()
    pids = out.decode().strip().split("\n")

    # If a process is running on the port, kill it
    if pids:
        for pid in pids:
            print(pid)
            # os.kill(int(pid), signal.SIGKILL)

    # Then, stop app_B
    if playground_process is not None:
        os.kill(playground_process.pid, signal.SIGTERM)

    return jsonify(success=True)


@app.route('/playground_restart', methods=['POST'])
@auth.login_required
def restart_app_playground():
    global playground_process

    # Get the process ID that occupies the port
    proc = subprocess.Popen(['lsof', '-t', '-i:5481'], stdout=subprocess.PIPE)
    out, err = proc.communicate()
    pid = out.decode().strip()

    # If a process is running on the port, kill it
    if pid:
        os.kill(int(pid), signal.SIGKILL)

    # Then, restart app_B
    if playground_process is not None and playground_process.poll() is None:
        playground_process.terminate()
        playground_process.wait()
    start_app_playground()
    return jsonify(success=True)

@app.route('/playground_status')
def status():
    status = is_playground_running()
    port_occupied = is_port_occupied(5481)
    return jsonify(running=status, port_occupied=port_occupied)


@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def home():
    if request.method == 'POST':
        role = request.form.get('role')
        name = request.form.get('name') if role == 'function' else None
        temperature = float(request.form.get('temperature'))
        content = request.form.get('content')

        messages_to_send = []
        if content != "":
            message = Message(role=role, name=name, content=content)
            db.session.add(message)
            db.session.commit()
            db.session.flush()
            messages_to_send.append(message)

        # Get selected messages
        for message in Message.query.all():
            if request.form.get(f'include_{message.id}'):
                messages_to_send.append(message)

        # Construct the 'messages' list for the OpenAI API call
        openai_messages = list()
        for message in messages_to_send:
            openai_messages.append(dict())
            openai_messages[-1]['role'] = message.role
            openai_messages[-1]['content'] = message.content
            if message.function_call and message.function_call != "null":
                openai_messages[-1]['function_call'] = json.loads(message.function_call)
            if message.name and message.name !="null":
                openai_messages[-1]['name'] = message.name

        # Clean up HTML content when applicable
        update_index = -1
        for i,om in enumerate(openai_messages):
            if "function_call" in om.keys() and om["function_call"]:
                if om["function_call"]["name"]=="search_status_update":
                    update_index = i
        last_content_index = -1
        for i,om in enumerate(openai_messages):
            if om["role"] == "function":
                if om["name"] == "get_url_page":
                    last_content_index = i
        if update_index>-1:
            for i, om in enumerate(openai_messages):
                if om["role"] == "function":
                    if om["name"] == "get_url_page" and i != last_content_index:
                        try:
                            d = json.loads(om['content'])
                            d["page_content"]="..."
                            om['content'] = json.dumps(d)
                        except Exception:
                            om['content'] = '...'

        print("*" * 80)
        for m in openai_messages:
            print(m)
        print("*" * 80)
        # Call to OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=openai_messages,
            temperature=temperature,
            functions=openai_functions_arg
        )

        # Add the assistant's response to the database
        print(response)
        # Fixing weirg OpenAI bug
        args = response['choices'][0]['message'].get("arguments")
        if args and args.endswith(",\n}"):
            args = args[-3:]+"}"
        assistant_message = Message(
            role='assistant',
            content=response['choices'][0]['message']['content'],
            function_call=json.dumps(response['choices'][0]['message'].get("function_call")),
            arguments=json.dumps(args),
        )
        db.session.add(assistant_message)
        db.session.commit()

        response_message = response['choices'][0]['message']
        if response_message.get("function_call"):
            function_name = response_message["function_call"]["name"]
            args = response['choices'][0]['message']["function_call"].get("arguments")
            # Fixing weird OpenAI bug
            if args and args.endswith(",\n}"):
                args = args[:-3] + '}'
            function_args = json.loads(args)
            function_answer = documented_functions[function_name][0](**function_args)
            print(function_name)
            print(function_args)
            print("__", function_answer)
            assistant_message = Message(
                role='function',
                name=function_name,
                content=json.dumps(function_answer),
            )
            db.session.add(assistant_message)
            db.session.commit()

    messages = Message.query.all()
    for message in messages:
        if message.function_call:
            message.function_call = json.loads(message.function_call)
        if message.content is None:
            if message.function_call:
                message.content = f"function call: {message.function_call['name']}\n"
                message.content += f"arguments:\n"
                print(message.function_call.get("arguments", {}))
                try:
                    for k,v in json.loads(message.function_call.get("arguments", {})).items():
                        message.content += f" * {k}: {repr(v)}"
                except json.decoder.JSONDecodeError:
                    message.content += str(message.function_call.get("arguments"))
            else:
                message.content = ""
        print("*", message.content)

    print(openai_functions_arg)
    return render_template('home.html',
                           messages=messages,
                           context=[{"title": i['name'], "content": i['description']} for i in openai_functions_arg],
                           playground_url=C.PLAYGROUND_URL)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host='0.0.0.0', port=5000)
    sleep(5)
