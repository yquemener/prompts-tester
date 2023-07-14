# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# The environment variable ensures that the python output is set straight
# to the terminal with out buffering it first
ENV PYTHONUNBUFFERED 1

RUN apt update
RUN apt install net-tools

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip
RUN pip install flask
RUN pip install matrix_client
RUN pip install openai
RUN pip install tiktoken
RUN pip install watchdog
RUN pip install Flask-HTTPAuth
RUN pip install Flask-SQLAlchemy
RUN pip install beautifulsoup4 html2text soupsieve

# Create root directory for our project in the container
RUN mkdir /app
RUN mkdir /app/data

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Start up Nginx server
CMD ["python", "main.py"]

