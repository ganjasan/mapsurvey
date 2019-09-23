FROM python:3.7-slim

# Set work directory
WORKDIR /code

#install geo libs
RUN apt-get update
RUN apt-get -y install binutils libproj-dev gdal-bin

#install postfix
RUN apt-get install -y postfix && \
postconf -e "myhostname = mail.mapsurvey.ru" && \
postconf -e "mydomain = mapsurvey.ru" && \
postconf -e "myorigin = $mydomain" && \
postconf -e "mydestination = localhost" && \


RUN pip install pipenv
COPY Pipfile Pipfile.lock /code/
RUN pipenv install --system

# Copy project
COPY . /code/