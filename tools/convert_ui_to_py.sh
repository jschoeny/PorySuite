#!/bin/zsh

source ./venv/bin/activate

# Change to the ui directory
cd ui || exit

# Iterate over all .ui files in the current directory
for file in *.ui; do
    # Extract filename without extension
    filename=$(basename -- "$file" .ui)
    # Define the corresponding Python file
    py_file="ui_$filename.py"

    # Check if .ui file is newer than .py file
    if [[ "$file" -nt "$py_file" || ! -e "$py_file" ]]; then
        # Run pyside6-uic
        pyside6-uic "$file" -o "$py_file"
        echo "Generated $py_file"
    fi
done
