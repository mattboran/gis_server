# syntax = docker/dockerfile:1.1-experimental
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

RUN mkdir -p /app
WORKDIR /app

COPY ./requirements.txt /app
RUN pip3 install -r requirements.txt

RUN pip3 install awscli

RUN --mount=type=secret,id=aws,target=/root/.aws/credentials aws s3 cp s3://gis-server-store/.env /app/.env
RUN --mount=type=secret,id=aws,target=/root/.aws/credentials aws s3 cp s3://gis-server-store/database.db /app/database.db

COPY ./app /app