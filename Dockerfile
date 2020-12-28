# syntax = docker/dockerfile:1.1-experimental
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

RUN mkdir -p /app
WORKDIR /app

COPY ./requirements.txt /app
RUN pip3 install -r requirements.txt

COPY ./app /app