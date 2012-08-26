#!/bin/bash
# install all schemas on sight
sudo cp *.gschema.xml /usr/share/glib-2.0/schemas/
sudo glib-compile-schemas /usr/share/glib-2.0/schemas/
