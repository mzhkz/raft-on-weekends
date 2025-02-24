# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

RUN pip install --upgrade pip
RUN apt-get update
RUN apt-get install -y libmpc-dev

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run run_node.py when the container launches
CMD ["python", "./raft/run_node.py"]
