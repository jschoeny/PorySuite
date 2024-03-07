#!/bin/zsh

source ./venv/bin/activate

# Change to the res directory
cd res || exit

# Iterate over all .qrc files in the current directory
for file in *.qrc; do
    # Extract filename without extension
    filename=$(basename -- "$file" .qrc)
    # Define the corresponding Python file
    py_file="${filename}_rc.py"

    # Check if .ui file is newer than .py file
    if [[ "$file" -nt "$py_file" || ! -e "$py_file" ]]; then
        # Run pyside6-rcc
        pyside6-rcc "$file" -o "$py_file"
        echo "Generated $py_file"
    fi
done
