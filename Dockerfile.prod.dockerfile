# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Update the package list and install net-tools
RUN apt-get update && apt-get install -y net-tools

RUN mkdir /app

# Install Poetry
RUN pip install poetry

# Set the working directory in the container
WORKDIR /app

# Copy the pyproject-old.toml and poetry.lock files into the container
COPY pyproject.toml poetry.lock /app/

# Install project dependencies using Poetry
RUN poetry install --no-dev

# Copy the rest of the application code into the container
COPY . /app

# Make port 80 available to the world outside this container
EXPOSE 5000

# Define the command to run your Flask app
CMD ["gunicorn"  , "-b", "0.0.0.0", "wsgi:app"]