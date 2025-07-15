# Start from the official Python image
FROM python:3.12

# Set environment variables for Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry'

# Install Poetry
RUN pip install poetry

# Set the working directory
WORKDIR /usr/src/app

# Download the wait-for-it.sh script before we need it
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh wait-for-it.sh

# Copy only the project definition file
# This will be used by Poetry to resolve and install dependencies
COPY pyproject.toml ./

# Install dependencies from pyproject.toml.
# This will also generate a poetry.lock file inside the container, but it won't be used in subsequent builds unless cached.
RUN poetry install --no-root --no-interaction

# Copy your application code and other necessary files
COPY . .

# Make scripts executable
RUN chmod +x wait-for-it.sh
RUN chmod +x entrypoint.sh

# Set the entrypoint for the container
ENTRYPOINT [ "./entrypoint.sh" ]

# Command to run your application
# CMD ["poetry", "run", "python", "-m", "gpt_agent"]