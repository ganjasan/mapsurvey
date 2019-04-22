FROM python:3.7-slim

# Set work directory
WORKDIR /code

#install geo libs
RUN apt-get update
RUN apt-get -y install binutils libproj-dev gdal-bin

RUN pip install pipenv
COPY Pipfile Pipfile.lock /code/
RUN pipenv install --system

# Copy project
COPY . /code/