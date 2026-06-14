# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Create a non-root user (Hugging Face Requirement)
RUN useradd -m -u 1000 user

# Install system dependencies required for OpenCV and Machine Learning
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Switch to the new user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set the working directory
WORKDIR /home/user/app

# Copy the entire project code into the container
COPY --chown=user . /home/user/app

# Upgrade PIP
RUN pip install --no-cache-dir --upgrade pip

# Install PRAHARI locally so the models work
RUN pip install --no-cache-dir -e .

# Install FastAPI and Web Server dependencies
RUN pip install --no-cache-dir fastapi uvicorn websockets python-multipart opencv-python-headless

# Hugging Face Spaces mandate exposing port 7860
EXPOSE 7860

# Start the FastAPI application on port 7860
CMD ["uvicorn", "frontend.backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
