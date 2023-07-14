#!/bin/bash

(cd playground; ./go.sh &)
flask --app app run  --debug -p 8080