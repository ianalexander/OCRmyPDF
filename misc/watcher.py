# Copyright (C) 2019 Ian Alexander: https://github.com/ianalexander
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import logging
from datetime import datetime
from pathlib import Path

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

import ocrmypdf

INPUT_DIRECTORY = os.getenv('OCR_INPUT_DIRECTORY', '/input')
OUTPUT_DIRECTORY = os.getenv('OCR_OUTPUT_DIRECTORY', '/output')
OUTPUT_DIRECTORY_YEAR_MONTH = bool(os.getenv('OCR_OUTPUT_DIRECTORY_YEAR_MONTH', False))
ON_SUCCESS_DELETE = bool(os.getenv('OCR_ON_SUCCESS_DELETE', False))
DESKEW = bool(os.getenv('OCR_DESKEW', False))
POLL_NEW_FILE_SECONDS = os.getenv('OCR_POLL_NEW_FILE_SECONDS', 1)
LOGLEVEL = os.environ.get('OCR_LOGLEVEL', 'INFO').upper()
PATTERNS = ['*.pdf']

logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger('ocrmypdf-watcher')

def execute_ocrmypdf(file_path):
    new_file = Path(file_path)
    filename = new_file.name
    if OUTPUT_DIRECTORY_YEAR_MONTH:
        today = datetime.today()
        output_directory_year_month = Path(
            f'{OUTPUT_DIRECTORY}/{today.year}/{today.month}'
        )
        if not output_directory_year_month.exists():
            output_directory_year_month.mkdir(parents=True, exist_ok=True)
        output_path = Path(output_directory_year_month) / filename
    else:
        output_path = Path(OUTPUT_DIRECTORY) / filename
    logger.info(f'New file: {file_path}. Waiting until fully loaded...')
    # This loop waits to make sure that the file is completely loaded on
    # disk before attempting to read. Docker sometimes will publish the
    # watchdog event before the file is actually fully on disk, causing
    # pikepdf to fail.
    current_size = None
    while current_size != new_file.stat().st_size:
        current_size = new_file.stat().st_size
        logger.debug(f'new_file current_size: {current_size}')
        time.sleep(POLL_NEW_FILE_SECONDS)
    logger.info(f'Attempting to OCRmyPDF to: {output_path}')
    exit_code = ocrmypdf.ocr(
        input_file=file_path, output_file=output_path, deskew=DESKEW
    )
    if exit_code == 0 and ON_SUCCESS_DELETE:
        logger.info(f'Done. Deleting: {file_path}')
        new_file.unlink()
    else:
        logger.info('Done')


class HandleObserverEvent(PatternMatchingEventHandler):
    def on_any_event(self, event):
        if event.event_type in ['created']:
            execute_ocrmypdf(event.src_path)


if __name__ == "__main__":
    logger.info(
        f"Starting OCRmyPDF watcher with config:\n"
        f"Input Directory: {INPUT_DIRECTORY}\n"
        f"Output Directory: {OUTPUT_DIRECTORY}\n"
        f"Output Directory Year & Month: {OUTPUT_DIRECTORY_YEAR_MONTH}"
    )
    logger.debug(
        f"INPUT_DIRECTORY: {INPUT_DIRECTORY}\n"
        f"OUTPUT_DIRECTORY: {OUTPUT_DIRECTORY}\n"
        f"OUTPUT_DIRECTORY_YEAR_MONTH: {OUTPUT_DIRECTORY_YEAR_MONTH}\n"
        f"ON_SUCCESS_DELETE: {ON_SUCCESS_DELETE}\n"
        f"DESKEW: {DESKEW}\n"
        f"POLL_NEW_FILE_SECONDS: {POLL_NEW_FILE_SECONDS}\n"
        f"LOGLEVEL: {LOGLEVEL}\n"
    )
    handler = HandleObserverEvent(patterns=PATTERNS)
    observer = Observer()
    observer.schedule(handler, INPUT_DIRECTORY, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
