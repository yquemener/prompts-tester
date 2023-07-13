import json

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import openai

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
openai.api_key = open("/home/yves/keys/openAIAPI", "r").read().rstrip("\n")


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


@app.route("/delete/<int:id>")
def delete(id):
    message = Message.query.get_or_404(id)
    db.session.delete(message)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/', methods=['GET', 'POST'])
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
        assistant_message = Message(
            role='assistant',
            content=response['choices'][0]['message']['content'],
            function_call=json.dumps(response['choices'][0]['message'].get("function_call")),
            arguments=json.dumps(response['choices'][0]['message'].get("arguments")),
        )
        db.session.add(assistant_message)
        db.session.commit()

        response_message = response['choices'][0]['message']
        if response_message.get("function_call"):
            function_name = response_message["function_call"]["name"]
            function_args = json.loads(response_message["function_call"]["arguments"])
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
                           context=[{"title": i['name'], "content": i['description']} for i in openai_functions_arg])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
