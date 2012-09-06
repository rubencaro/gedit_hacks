#!/bin/bash
# [Gedit Tool]
# Name=Grep on project
# Shortcut=<Control><Shift>f
# Applicability=all
# Output=output-panel
# Input=selection
# Save-files=nothing

# Executes grep of selection on detected project folder, on
# detected RVM gemset folder, or on document's path by default.
# It does it all in a new terminal with 'Default' profile.
#  (depends on grep, zenity)
#  (recommends git for project detection,
#  and RVM for gemset detection)
#
# Save:   Nothing
# Input:  Selection
# Output: Nothing
#
# by Rubén Caro (ruben.caro@lanuez.org), edited by (you?)

read SELECTION

# allow to refine expression
EXPRESSION=$(zenity --entry --text='Expression to grep' --entry-text="$SELECTION")

if [[ ! '0' = "$?" || '' = "$EXPRESSION" ]]; then # cancelled
  echo "Cancelled."
  exit 0
fi

# add document dir
GREP_PATHS=$GEDIT_CURRENT_DOCUMENT_DIR

# try to replace with git project dir
PROJ_DIR=$(git rev-parse --show-toplevel 2> /dev/null)
if [ ! '' = "$PROJ_DIR" ]; then
  GREP_PATHS="$PROJ_DIR"
fi

# try to load gemset and add gemset dir
source $HOME/.rvm/scripts/rvm &> /dev/null
cd $GEDIT_CURRENT_DOCUMENT_DIR &> /dev/null
GEMSET_DIR=$(gem env gemdir)
if [ ! '' = "$GEMSET_DIR" ]; then
  GREP_PATHS="$GREP_PATHS $GEMSET_DIR"
fi

# some annoying output (to be customized...)
EXCLUDES="--exclude-dir=.git --exclude=Makefile --exclude=*~"

# clean output for gedit to be able to open file:line references
SED_CLEAN="sed 's/\(.*:[0-9]\+:\)\(.*\)/\1 \2/'"

GREP_COMMAND="grep -RnwI $EXCLUDES '$EXPRESSION' $GREP_PATHS | $SED_CLEAN "

bash -l -c "$GREP_COMMAND"

echo
echo "--- Searched for '$EXPRESSION' inside:"
echo $GREP_PATHS
