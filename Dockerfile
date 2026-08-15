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
RUN apt-get -y install apt-utils binutils libproj-dev gdal-bin postgresql-client
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

# Collect static assets into the image rather than at container start. Hashing and
# compressing 500+ assets through CompressedManifestStaticFilesStorage took tens of
# seconds on every Render start, inside the deploy's 502 window (the service mounts a
# disk, so Render cannot run old and new instances side by side). It needs no secrets:
# settings.py defaults SECRET_KEY, and collectstatic touches no database.
#
# Side benefit: a dangling {% static %} reference now fails the build instead of the
# already-committed production deploy.
#
# Must stay above the chown, so the generated tree is owned by `app` like everything else.
RUN python manage.py collectstatic --no-input

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

ENTRYPOINT ["/home/app/web/entrypoint.sh"]
CMD gunicorn --bind :${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --worker-class gthread --timeout ${GUNICORN_TIMEOUT:-60} mapsurvey.wsgi:application

