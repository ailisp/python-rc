FROM python:3.6

RUN pip install pipenv

WORKDIR /root
RUN curl https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-289.0.0-linux-x86_64.tar.gz -o gcloud.tar.gz
RUN tar zxf gcloud.tar.gz
ENV PATH /root/google-cloud-sdk/bin:$PATH

WORKDIR /root/bin
RUN curl -L https://github.com/digitalocean/doctl/releases/download/v1.41.0/doctl-1.41.0-linux-amd64.tar.gz -o doctl.tar.gz
RUN tar zxf doctl.tar.gz
ENV PATH /root/bin:$PATH

WORKDIR /root/python-rc

COPY ./Pipfile .
COPY ./Pipfile.lock .

RUN pipenv sync

COPY . .
