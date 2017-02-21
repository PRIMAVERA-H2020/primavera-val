# (C) British Crown Copyright 2017, Met Office.
# Please see LICENSE.rst for license details.
"""
primavera-val

Simple data validation tests for PRIMAVERA stream 1 data files.

Requires:
    Iris: http://scitools.org.uk/iris/
        Tested under Iris 1.10 as installed at JASMIN
"""
import logging
import os
import random

import iris
from iris.time import PartialDateTime

DEFAULT_LOG_LEVEL = logging.WARNING
DEFAULT_LOG_FORMAT = '%(levelname)s: %(message)s'

logger = logging.getLogger(__name__)


FREQUENCY_VALUES = ['ann', 'mon', 'day', '6hr', '3hr', '1hr', 'subhr', 'fx']


class FileValidationError(Exception):
    """
    An exception to indicate that a data file has failed validation.
    """
    pass


def identify_filename_metadata(filename, file_format='CMIP6'):
    """
    Identify all of the required metadata from the filename and file contents

    :param str filename: The file's complete path
    :param str file_format: The CMOR version of the netCDF files, one out of-
        CMIP5 or CMIP6
    :returns: A dictionary containing the identified metadata
    :raises FileValidationError: If unable to parse the date string
    """
    if file_format == 'CMIP5':
        components = ['cmor_name', 'table', 'climate_model', 'experiment',
                      'rip_code', 'date_string']
    elif file_format == 'CMIP6':
        components = ['cmor_name', 'table', 'experiment', 'climate_model',
                      'rip_code', 'grid', 'date_string']
    else:
        raise NotImplementedError('file_format must be CMIP5 or CMIP6')

    basename = os.path.basename(filename)
    directory = os.path.dirname(filename)
    metadata = {'basename': basename, 'directory': directory}

    # split the filename into sections
    filename_sects = basename.rstrip('.nc').split('_')

    # but if experiment present_day was in the filename, join these sections
    # back together
    if filename_sects[3] == 'present' and filename_sects[4] == 'day':
        filename_sects[3] += '_' + filename_sects.pop(4)

    # deduce as much as possible from the filename
    try:
        for cmpt_name, cmpt in zip(components, filename_sects):
            if cmpt_name == 'date_string':
                start_date, end_date = cmpt.split('-')
                try:
                    metadata['start_date'] = _make_partial_date_time(start_date)
                    metadata['end_date'] = _make_partial_date_time(end_date)
                except ValueError:
                    msg = 'Unknown date format in filename: {}'.format(filename)
                    logger.debug(msg)
                    raise FileValidationError(msg)
            else:
                metadata[cmpt_name] = cmpt
    except ValueError:
        msg = 'Unknown filename format: {}'.format(filename)
        logger.debug(msg)
        raise FileValidationError(msg)

    metadata['filesize'] = os.path.getsize(filename)

    for freq in FREQUENCY_VALUES:
        if freq in metadata['table'].lower():
            metadata['frequency'] = freq
            break
    if 'frequency' not in metadata:
        # set a blank frequency if one hasn't been found
        metadata['frequency'] = ''

    return metadata


def identify_contents_metadata(cube, filename):
    """
    Uses Iris to get additional metadata from the files contents

    :param iris.cube.Cube cube: The loaded file to check
    :param str filename: the name of the file that the cube was loaded from
    :returns: A dictionary of the identified metadata
    """
    metadata = {}

    try:
        # This could be None if cube.var_name isn't defined
        metadata['var_name'] = cube.var_name
        metadata['units'] = str(cube.units)
        metadata['long_name'] = cube.long_name
        metadata['standard_name'] = cube.standard_name
        metadata['time_units'] = cube.coord('time').units.origin
        metadata['calendar'] = cube.coord('time').units.calendar
        # CMIP5 doesn't have an activity id and so supply a default
        metadata['activity_id'] = cube.attributes.get('activity_id',
                                                      'HighResMIP')
        try:
            metadata['institute'] = cube.attributes['institution_id']
        except KeyError:
            # CMIP5 uses institute_id but we should not be processing CMIP5
            # data but handle it just in case
            metadata['institute'] = cube.attributes['institute_id']
    except Exception as exc:
        msg = ('Unable to extract metadata from the contents of file {}\n{}'.
               format(filename, exc.message))
        logger.error(msg)
        raise FileValidationError(msg)

    return metadata


def validate_file_contents(cube, metadata):
    """
    Check whether the contents of the cube loaded from a file are valid

    :param iris.cube.Cube cube: The loaded file to check
    :param dict metadata: Metadata obtained from the file
    :returns: A boolean
    """
    _check_start_end_times(cube, metadata)
    _check_contiguity(cube, metadata)
    _check_data_point(cube, metadata)


def load_cube(filename):
    """
    Loads the specified file into a single Iris cube

    :param str filename: The path of the file to load
    :returns: An Iris cube containing the loaded file
    :raises FileValidationError: If the file generates more than a single cube
    """
    iris.FUTURE.netcdf_promote = True

    try:
        cubes = iris.load(filename)
    except Exception:
        msg = 'Unable to load data from file: {}'.format(filename)
        logger.debug(msg)
        raise FileValidationError(msg)

    var_name = os.path.basename(filename).split('_')[0]

    var_cubes = cubes.extract(iris.Constraint(cube_func=lambda cube:
                                              cube.var_name == var_name))

    if not var_cubes:
        msg = ("Filename '{}' does not load to a single variable".
               format(filename))
        logger.debug(msg)
        raise FileValidationError(msg)

    return var_cubes[0]


def list_files(directory, suffix='.nc'):
    """
    Return a list of all the files with the specified suffix in the submission
    directory structure and sub-directories.

    :param str directory: The root directory of the submission
    :param str suffix: The suffix of the files of interest
    :returns: A list of absolute filepaths
    """
    nc_files = []

    dir_files = os.listdir(directory)
    for filename in dir_files:
        file_path = os.path.join(directory, filename)
        if os.path.isdir(file_path):
            nc_files.extend(list_files(file_path))
        elif file_path.endswith(suffix):
            nc_files.append(file_path)

    return nc_files


def _make_partial_date_time(date_string):
    """
    Convert the fields in `date_string` into a PartialDateTime object. Formats
    that are known about are:

    YYYMM
    YYYYMMDD

    :param str date_string: The date string to process
    :returns: An Iris PartialDateTime object containing as much information as
        could be deduced from date_string
    :rtype: iris.time.PartialDateTime
    :raises ValueError: If the string is not in a known format.
    """
    if len(date_string) == 6:
        pdt_str = PartialDateTime(year=int(date_string[0:4]),
                                  month=int(date_string[4:6]))
    elif len(date_string) == 8:
        pdt_str = PartialDateTime(year=int(date_string[0:4]),
                                  month=int(date_string[4:6]),
                                  day=int(date_string[6:8]))
    else:
        raise ValueError('Unknown date string format')

    return pdt_str


def _check_start_end_times(cube, metadata):
    """
    Check whether the start and end dates match those in the metadata

    :param iris.cube.Cube cube: The loaded file to check
    :param dict metadata: Metadata obtained from the file
    :returns: True if the times match
    :raises FileValidationError: If the times don't match
    """
    file_start_date = metadata['start_date']
    file_end_date = metadata['end_date']

    time = cube.coord('time')
    data_start = time.units.num2date(time.points[0])
    data_end = time.units.num2date(time.points[-1])

    if file_start_date != data_start:
        msg = ('Start date in filename does not match the first time in the '
               'file ({}): {}'.format(str(data_start), metadata['basename']))
        logger.debug(msg)
        raise FileValidationError(msg)
    elif file_end_date != data_end:
        msg = ('End date in filename does not match the last time in the '
               'file ({}): {}'.format(str(data_end), metadata['basename']))
        logger.debug(msg)
        raise FileValidationError(msg)
    else:
        return True


def _check_contiguity(cube, metadata):
    """
    Check whether the time coordinate is contiguous

    :param iris.cube.Cube cube: The loaded file to check
    :param dict metadata: Metadata obtained from the file
    :returns: True if the data is contiguous
    :raises FileValidationError: If the data isn't contiguous
    """
    time_coord = cube.coord('time')

    if not time_coord.is_contiguous():
        msg = ('The points in the time dimension in the file are not '
               'contiguous: {}'.format(metadata['basename']))
        logger.debug(msg)
        raise FileValidationError(msg)
    else:
        return True


def _check_data_point(cube, metadata):
    """
    Check whether a data point can be loaded

    :param iris.cube.Cube cube: The loaded file to check
    :param dict metadata: Metadata obtained from the file
    :returns: True if a data point was read without any exceptions being raised
    :raises FileValidationError: If there was a problem reading the data point
    """
    point_index = []

    for dim_length in cube.shape:
        point_index.append(int(random.random() * dim_length))

    point_index = tuple(point_index)

    try:
        _data_point = cube.data[point_index]
    except Exception:
        msg = 'Unable to extract data point {} from file: {}'.format(
            point_index, metadata['basename'])
        logger.debug(msg)
        raise FileValidationError(msg)
    else:
        return True
