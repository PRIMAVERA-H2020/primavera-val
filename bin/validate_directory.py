#!/usr/bin/env python2.7
# (C) British Crown Copyright 2017, Met Office.
# Please see LICENSE.rst for license details.
"""
SYNOPSIS

    validate_directory.py [-h] [-f FILE_FORMAT] [-l LOG_LEVEL] directory

DESCRIPTION

    A simple data validation test for PRIMAVERA stream 1 data files. The
    following checks are performed on all files with a .nc suffix in the
    directories below the top-level directory:

        1. filenames are correctly formatted
        2. that essential metadata items can be read from each file's contents
        3. the start and end times in the filenames match those in the files
        4. the data is contiguous
        5. that a random data point can be read from each file

ARGUMENTS

    directory
        the top-level directory of the files to check

OPTIONS

    -h, --help
        display a usage message
    -f, --file-format
        the CMOR version of the input netCDF files to be validated
        (CMIP5 or CMIP6) (default: CMIP6)
    -l LOG_LEVEL, --log-level LOG_LEVEL
        set logging level to one of debug, info, warn (the default), or error

ENVIRONMENT VARIABLES

    The primavera-val directory must be in PYTHONPATH

DEPENDENCIES:
    Iris:
        http://scitools.org.uk/iris/ Tested under Iris 1.10 as installed at
        JASMIN
"""
import argparse
import logging
import os
import sys

from primavera_val import (identify_filename_metadata, load_cube, list_files,
                           identify_contents_metadata, validate_file_contents,
                           FileValidationError)

DEFAULT_LOG_LEVEL = logging.WARNING
DEFAULT_LOG_FORMAT = '%(levelname)s: %(message)s'

logger = logging.getLogger(__name__)


def parse_args():
    """
    Parse command-line arguments
    """
    parser = argparse.ArgumentParser(description='Validate a directory of '
                                                 'PRIMAVERA data ')
    parser.add_argument('directory', help='the top-level directory of the '
                                          'files to check')
    parser.add_argument('-f', '--file-format', default='CMIP6',
                        help='the CMOR version of the input netCDF files '
                             'being submitted (CMIP5 or CMIP6) (default: '
                             '%(default)s)')
    parser.add_argument('-l', '--log-level', help='set logging level to one '
                                                  'of debug, info, warn (the '
                                                  'default), or error')
    args = parser.parse_args()

    return args


def main(args):
    """
    Run the checks
    """
    # the metadata found by the checks is used in the online PRIMAVERA
    # validation but can be ignored in this simple check
    _output = []

    num_errors_found = 0

    data_files = list_files(os.path.expandvars(
        os.path.expanduser(args.directory)))
    if not data_files:
        msg = 'No data files found in directory: {}'.format(args.directory)
        logger.error(msg)
        sys.exit(1)

    logger.debug('%s files found.', len(data_files))

    for filename in data_files:
        try:
            # run the four checks that the validate script runs
            metadata = identify_filename_metadata(filename, args.file_format)
            cube = load_cube(filename)
            metadata.update(identify_contents_metadata(cube, filename))
            validate_file_contents(cube, metadata)
        except FileValidationError as exc:
            logger.warning('File failed validation:\n%s', exc.message)
            num_errors_found += 1
        else:
            _output.append(metadata)

    if num_errors_found:
        logger.error('%s files failed validation', num_errors_found)
        sys.exit(1)
    else:
        logger.debug('All files successfully validated.')
        sys.exit(0)


if __name__ == '__main__':
    cmd_args = parse_args()

    # Disable propagation and discard any existing handlers.
    logger.propagate = False
    if len(logger.handlers):
        logger.handlers = []

    # set-up the logger
    console = logging.StreamHandler(stream=sys.stdout)
    fmtr = logging.Formatter(fmt=DEFAULT_LOG_FORMAT)
    if cmd_args.log_level:
        try:
            logger.setLevel(getattr(logging, cmd_args.log_level.upper()))
        except AttributeError:
            logger.setLevel(logging.WARNING)
            logger.error('log-level must be one of: debug, info, warn or '
                         'error')
            sys.exit(1)
    else:
        logger.setLevel(DEFAULT_LOG_LEVEL)
    console.setFormatter(fmtr)
    logger.addHandler(console)

    # run the code
    main(cmd_args)
