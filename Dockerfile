# pull official base image
FROM python:3.9-slim 

# create directory for the app user
RUN mkdir -p /home/app

# create the app user
RUN addgroup --system app && adduser --system app && adduser app app

# create the appropriate directories
ENV HOME=/home/app
ENV APP_HOME=/home/app/web/
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

#install geo libs
RUN apt-get -y update && apt-get -y upgrade
RUN apt-get -y install apt-utils binutils libproj-dev gdal-bin netcat postgresql-client
RUN apt-get -y install openssh-server

# install dependencies
RUN pip install pipenv
COPY Pipfile Pipfile.lock $APP_HOME
RUN pipenv install --system

EXPOSE 8000

# copy entrypoint.sh and add execute permission
COPY ./entrypoint.sh $APP_HOME
RUN ["chmod", "u+x", "/home/app/web/entrypoint.sh"]

# copy project
COPY . $APP_HOME

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

# run entrypoint.prod.sh
#ENTRYPOINT ["/home/app/web/entrypoint.sh"]

