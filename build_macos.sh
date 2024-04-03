#!/bin/zsh
pyinstaller --onefile -i "./images/bulk_creator_icon.icns" -n "P4 Bulk Creator (MacOS arm64)" --distpath ./bin ./app/main.py