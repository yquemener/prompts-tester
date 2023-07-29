# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# The environment variable ensures that the python output is set straight
# to the terminal with out buffering it first
ENV PYTHONUNBUFFERED 1

RUN mkdir /app
RUN mkdir /app/data
WORKDIR /app
COPY requirements.txt /app/requirements.txt

RUN apt update
RUN apt install -y net-tools
RUN pip install --upgrade pip
RUN pip install flask gunicorn matrix_client openai tiktoken watchdog Flask-HTTPAuth Flask-SQLAlchemy beautifulsoup4 html2text soupsieve
RUN pip install -r requirements.txt

COPY . /app


CMD ["python", "main.py"]

