#!/bin/bash

IMAGE=mahno
IMAGE_L=registry.gitlab.com/kdudkov/$IMAGE

TAG=latest

tar czf files.tar.gz actors config core static requirements.txt *.py
docker build . -t $IMAGE_L:$TAG -t $IMAGE:$TAG
rm files.tar.gz

docker push $IMAGE_L:$TAG
