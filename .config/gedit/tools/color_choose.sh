#!/bin/sh
# [Gedit Tool]
# Name=Color choose
# Shortcut=<Primary><Shift>o
# Applicability=all
# Output=replace-selection
# Input=selection
# Save-files=nothing

read SELECTION
COLOR=$(yad --color --init-color="$SELECTION")

if [ "" = "$COLOR" ]; then
	echo "$SELECTION"
else
	echo "$COLOR"
fi
