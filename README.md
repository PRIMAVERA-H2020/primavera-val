[![Build Status](https://travis-ci.com/PRIMAVERA-H2020/primavera-val.svg?branch=master)](https://travis-ci.com/PRIMAVERA-H2020/primavera-val)
# primavera-val

&copy; Copyright 2019, PRIMAVERA.
Please see LICENSE for license details.


A simple data validation test for PRIMAVERA stream 1 data files. The following
checks are performed on all files with a .nc suffix in the directories below
the directory specified, or on the file specified if using the -s option:

1. filenames are correctly formatted
2. that essential metadata items can be read from each file's contents
3. the start and end times in the filenames match those in the files
4. the data is contiguous
5. that a random data point can be read from each file

#### Usage
```
usage: validate_data.py [-h] [-f FILE_FORMAT] [-s] [-c] [-l LOG_LEVEL]
                        directory

Validate a directory of PRIMAVERA data

positional arguments:
  directory             the top-level directory containing the files to check

optional arguments:
  -h, --help            show this help message and exit
  -f FILE_FORMAT, --file-format FILE_FORMAT
                        the CMOR version of the input netCDF files being
                        submitted (CMIP5 or CMIP6) (default: CMIP6)
  -s, --single-file     validate a single specified file rather than a
                        directory
  -c, --cell-measure    file is a cell measure
  -l LOG_LEVEL, --log-level LOG_LEVEL
                        set logging level to one of debug, info, warn (the
                        default), or error
```
#### Return Values
`0` if all files validated successfully

`1` if any files failed validation

To get a message displayed showing if files passed validation use the
`-l debug` option.


#### Requires

Iris (http://scitools.org.uk/iris/) Tested under Iris 1.13 as installed at JASMIN and Iris 2.1.

#### Environment Variables

The `PYTHONPATH` environment variable must include the primavera-val directory.
