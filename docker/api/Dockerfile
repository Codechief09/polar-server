# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.9-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install libgl for opencv
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y libgl1-mesa-dev
RUN apt-get install -y libopencv-dev
RUN apt-get install -y poppler-utils
RUN apt-get install -y poppler-data
RUN apt-get install -y nodejs
RUN apt-get install -y locales
RUN sed -i -E 's/# (ja_JP.UTF-8)/\1/' /etc/locale.gen
RUN locale-gen
RUN update-locale LANG=ja_JP.UTF-8
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8

# Install source han sans jp
RUN apt-get install -y curl
RUN apt-get install -y unzip
RUN curl -o /tmp/SourceHanSansJP.zip -O -L https://github.com/adobe-fonts/source-han-code-jp/archive/2.011R.zip && \
    mkdir -p /usr/share/fonts/opentype/adobe/sourcehansans && \
    unzip -d /usr/share/fonts/opentype/adobe/sourcehansans/ /tmp/SourceHanSansJP.zip && \
    rm -rf /usr/share/fonts/opentype/adobe/sourcehansans/source-han-code-jp-2.011R/OTC && \
    fc-cache -fv

RUN echo '<?xml version="1.0"?>' > /etc/fonts/local.conf
RUN echo '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">' >> /etc/fonts/local.conf
RUN echo '<fontconfig>' >> /etc/fonts/local.conf
RUN echo '    <match target="pattern">' >> /etc/fonts/local.conf
RUN echo '        <test name="lang">' >> /etc/fonts/local.conf
RUN echo '            <string>ja</string>' >> /etc/fonts/local.conf
RUN echo '        </test>' >> /etc/fonts/local.conf
RUN echo '        <edit name="family" mode="prepend">' >> /etc/fonts/local.conf
RUN echo '            <string>Source Han Code JP</string>' >> /etc/fonts/local.conf
RUN echo '        </edit>' >> /etc/fonts/local.conf
RUN echo '    </match>' >> /etc/fonts/local.conf
RUN echo '</fontconfig>' >> /etc/fonts/local.conf

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 flask_main:app
