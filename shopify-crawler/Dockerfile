FROM python:3.7.2-alpine

LABEL name="shopify-crawler" \
    description="Shopify Crawler Instance" \
    maintainer="Ritesh Kadmawala <ritesh@vertexcover.io>"


# ARG GIT_COMMIT_HASH

# ENV GIT_COMMIT_HASH $GIT_COMMIT_HASH

# ARG GIT_BRANCH

# ENV GIT_BRANCH $GIT_BRANCH

WORKDIR /app

## Install gcc
RUN apk update && apk add g++ python3-dev musl-dev linux-headers libffi libffi-dev libressl-dev --no-cache

## Copy pyproject.*
COPY pyproject.toml poetry.lock ./

# Install dependencies

## HACK: Install google-cloud-firestore separately, because one of its dependency is grpcio
# and it has bug in its requires metadata which causes poetry to add  enum34
# as one of its dependencies which doesn't work on python 3.6
## So we install grpcio and google-cloud-firestore separately outside poetry.

RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir grpcio google-cloud-firestore poetry \
    && poetry config settings.virtualenvs.create false \
    && poetry install --no-dev \
    && pip3 uninstall --yes poetry

## Copy the entire app
COPY . ./

ENV GOOGLE_APPLICATION_CREDENTIALS /root/.config/shopify-crawler-creds.json

CMD ["./cli.py", "crawl"]
