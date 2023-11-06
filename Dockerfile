# Start with a Python 3.9 base image
FROM python:3.9-slim

# Install necessary libraries for GUI support
RUN apt-get update && apt-get install -y python3-tk x11-apps

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the environment variable for OpenAI API key
# (you'll need to provide the actual key when running the container)
ENV OPENAI_API_KEY=

# Expose the port for visualizer/app.py
EXPOSE 8000

ARG DEFAULT_CMD=
ENV COMMAND=${DEFAULT_CMD:-/bin/bash}
CMD ${COMMAND}
