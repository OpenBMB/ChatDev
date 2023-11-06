# Start with a Python 3.9 base image
FROM python:3.9-slim

# Install necessary libraries for GUI support
RUN apt-get update && apt-get install -y python3-tk x11-apps

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# No need to copy the rest of the application code as we use bind mounts
# COPY . .

# Expose the port for online_log/app.py
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/python3"]
CMD ["online_log/app.py"]
