FROM python:3.6

RUN pip install pipenv

WORKDIR /root
RUN curl https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-289.0.0-linux-x86_64.tar.gz -o gcloud.tar.gz
RUN tar zxf gcloud.tar.gz

WORKDIR /root/python-rc

COPY ./Pipfile .
COPY ./Pipfile.lock .

RUN pipenv sync

COPY . .
