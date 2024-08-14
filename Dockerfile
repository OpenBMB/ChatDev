# Start with a Python 3.9 base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the environment variable for OpenAI API key
# (you'll need to provide the actual key when running the container)
ENV OPENAI_API_KEY=your_OpenAI_API_key

# Set the environment variable for Groq API key
# (you'll need to provide the actual key when running the container)
ENV GROQ_API_KEY=your_Groq_API_key

# Expose the port for visualizer/app.py
EXPOSE 8000

# Set an entry point that runs a shell for interactive mode
ENTRYPOINT ["/bin/bash"]