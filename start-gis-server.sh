#!/usr/bin/env bash

docker stop $GIS_SERVER
docker rm $GIS_SERVER
docker run \
    --name $GIS_SERVER \
    --restart always \
    -p 8000:80 \
    -v $GIS_SERVER_DIR/app:/app \
    -d \
    docker.pkg.github.com/mattboran/gis_server/gis_server:latest
