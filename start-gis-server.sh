#!/usr/bin/env bash
GIS_SERVER="gis_server"
GIS_SERVER_DIR="$HOME/$GIS_SERVER"

docker stop $GIS_SERVER 2>/dev/null
docker rm $GIS_SERVER 2>/dev/null
docker run \
    --name $GIS_SERVER \
    -p 8000:80 \
    -v $GIS_SERVER_DIR/app:/app \
    -d \
    docker.pkg.github.com/mattboran/gis_server/gis_server:latest
