# (C) British Crown Copyright 2017, Met Office.
# Please see LICENSE.rst for license details.
"""
primavera-val

Simple data validation tests for PRIMAVERA stream 1 data files.

Requires:
    Iris: http://scitools.org.uk/iris/
        Tested under Iris 1.10 as installed at JASMIN
"""
from __future__ import unicode_literals, division, absolute_import
import datetime
import os
import random
import re

import iris
from iris.time import PartialDateTime


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
        components = ['cmor_name', 'table', 'climate_model', 'experiment',
                      'rip_code', 'grid', 'date_string']
    else:
        raise NotImplementedError('file_format must be CMIP5 or CMIP6')

    basename = os.path.basename(filename)
    directory = os.path.dirname(filename)
    metadata = {'basename': basename, 'directory': directory}

    # split the filename into sections
    if basename.endswith('-clim.nc'):
        filename_sects = basename.rpartition('-clim.nc')[0].split('_')
    else:
        filename_sects = basename.rpartition('.nc')[0].split('_')

    # but if experiment present_day was in the filename, join these sections
    # back together. This should only occur in pre-PRIMAVERA data.
    if filename_sects[3] == 'present' and filename_sects[4] == 'day':
        filename_sects[3] += '_' + filename_sects.pop(4)

    # deduce as much as possible from the filename
    try:
        for cmpt_name, cmpt in zip(components, filename_sects):
            if cmpt_name == 'date_string':
                frequency = _get_frequency(metadata['table'])
                start_date, end_date = cmpt.split('-')
                try:
                    metadata['start_date'] = _make_partial_date_time(
                        start_date, frequency)
                    metadata['end_date'] = _make_partial_date_time(
                        end_date, frequency)
                except ValueError:
                    msg = 'Unknown date format in filename: {}'.format(
                        filename)
                    raise FileValidationError(msg)
            else:
                metadata[cmpt_name] = cmpt
    except ValueError:
        msg = 'Unknown filename format: {}'.format(filename)
        raise FileValidationError(msg)

    # fixed variables won't have a time range and so create blank values
    potential_missing_values = ['start_date', 'end_date']
    for missing_value in potential_missing_values:
        if missing_value not in metadata:
            metadata[missing_value] = None

    metadata['filesize'] = os.path.getsize(filename)

    for freq in FREQUENCY_VALUES:
        if freq in metadata['table'].lower():
            metadata['frequency'] = freq
            break
    if 'frequency' not in metadata:
        # set a blank frequency if one hasn't been found
        metadata['frequency'] = ''

    return metadata


def identify_cell_measures_metadata(cfreader, filename):
    """
    Get metadata information from a cell measures variable.

    :param iris.fileformats.cf.CFReader cfreader: The CF metadata from
        `filename`
    :param str filename: The name of the file to gather information from
    :returns: A dictionary of the identified metadata.
    """
    metadata = {}

    try:
        # This could be None if cube.var_name isn't defined
        cmor_name = os.path.basename(filename).split('_')[0]
        metadata['var_name'] = cmor_name
        metadata['units'] = str(cfreader.cf_group[cmor_name].
                                getncattr('units'))
        metadata['long_name'] = cfreader.cf_group[cmor_name].getncattr(
            'long_name')
        metadata['standard_name'] = cfreader.cf_group[cmor_name].getncattr(
            'standard_name')
        metadata['time_units'] = None
        metadata['calendar'] = None
        # CMIP5 doesn't have an activity id and so supply a default
        metadata['activity_id'] = cfreader.cf_group.global_attributes.get(
            'activity_id', 'HighResMIP')
        try:
            metadata['institute'] = (cfreader.cf_group.
                                     global_attributes['institution_id'])
        except KeyError:
            # CMIP5 uses institute_id but we should not be processing CMIP5
            # data but handle it just in case
            metadata['institute'] = (cfreader.cf_group.
                                     global_attributes['institute_id'])
    except Exception as exc:
        msg = ('Unable to extract metadata from the contents of file {}\n{}'.
               format(filename, exc.__str__()))
        raise FileValidationError(msg)

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
               format(filename, exc.__str__()))
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


def validate_cell_measures_contents(cfreader, metadata):
    """
    Check whether the contents of the cube loaded from a file are valid

    :param iris.fileformats.cf.CFReader cfreader: The CF metadata from the
        file
    :param dict metadata: Metadata obtained from the file
    :returns: A boolean
    """
    _check_cell_measure_point(cfreader, metadata)


def load_cube(filename):
    """
    Loads the specified file into a single Iris cube

    :param str filename: The path of the file to load
    :returns: An Iris cube containing the loaded file
    :raises FileValidationError: If the file generates more than a single cube
    """
    try:
        try:
            cubes = iris.load(filename)
        except AttributeError:
            # Until https://github.com/SciTools/iris/pull/2485 is complete
            # add this fix for certain hybrid height (model level) variables
            cubes = iris.load_raw(filename)
            bounds_cubes = iris.cube.CubeList()
            data_cube = None
            for cube in cubes:
                if cube.var_name.endswith('_bnds'):
                    bounds_cubes.append(cube)
                else:
                    data_cube = cube
            if not bounds_cubes or not data_cube:
                msg = ('Unable to find data and bounds when fixing hybrid '
                       'height bounds in file: {}'.format(filename))
                raise FileValidationError(msg)
            for bounds_cube in bounds_cubes:
                coord_name = bounds_cube.long_name.replace('+1/2', '')
                bounds_coord = data_cube.coord(coord_name)
                bounds_coord.bounds = bounds_cube.data
            cubes = iris.cube.CubeList([data_cube])
    except Exception:
        msg = 'Unable to load data from file: {}'.format(filename)
        raise FileValidationError(msg)

    var_name = os.path.basename(filename).split('_')[0]

    var_cubes = cubes.extract(iris.Constraint(cube_func=lambda lcube:
                                              lcube.var_name == var_name))

    if not var_cubes:
        msg = ("Filename '{}' does not load to a single variable".
               format(filename))
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


def _get_frequency(table_name):
    """
    Finds the frequency of the data in the specified table name.

    :param str table_name: The name of the table
    :returns: The frequency of the data in the table
    :rtype: str
    :raises ValueError: If no frequency can be found in the table name
    """
    # remove Prim from the start of table names as this is not in capitals
    if table_name.startswith('Prim'):
        fixed_primavera = table_name[4:]
    else:
        fixed_primavera = table_name

    # The frequency is the first group of lower-case characters and digits in
    # the table name.
    components = re.search(r'[a-z\d]+', fixed_primavera)
    if components:
        return components.group(0)
    else:
        raise ValueError('Unable to calculate frequency from table name {}'.
                         format(table_name))


def _make_partial_date_time(date_string, frequency):
    """
    Convert the fields in `date_string` into a PartialDateTime object. Formats
    that are known about are:

    YYYMM
    YYYYMMDD

    :param str date_string: The date string to process
    :param str frequency: The frequency of data in the file
    :returns: An Iris PartialDateTime object containing as much information as
        could be deduced from date_string
    :rtype: iris.time.PartialDateTime
    :raises ValueError: If the string is not in a known format.
    """
    if frequency in ('yr', 'dec'):
        pdt = PartialDateTime(year=int(date_string[0:4]))
    elif frequency == 'mon':
        pdt = PartialDateTime(year=int(date_string[0:4]),
                              month=int(date_string[4:6]))
    elif frequency == 'day':
        pdt = PartialDateTime(year=int(date_string[0:4]),
                              month=int(date_string[4:6]),
                              day=int(date_string[6:8]))
    elif frequency in ('6hr', '3hr', '1hr', 'hr'):
        pdt = PartialDateTime(year=int(date_string[0:4]),
                              month=int(date_string[4:6]),
                              day=int(date_string[6:8]),
                              hour=int(date_string[8:10]),
                              minute=int(date_string[10:12]))
    elif frequency == 'subhr':
        pdt = PartialDateTime(year=int(date_string[0:4]),
                              month=int(date_string[4:6]),
                              day=int(date_string[6:8]),
                              hour=int(date_string[8:10]),
                              minute=int(date_string[10:12]),
                              second=int(date_string[12:14]))
    else:
        raise ValueError('Unsupported frequency string {}'.format(frequency))

    return pdt


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
    if metadata['basename'].endswith('-clim.nc'):
        # climatology so use bounds
        data_start = time.units.num2date(time.bounds[0][0])
        data_end = time.units.num2date(time.bounds[-1][1])
    else:
        # normal data so use points
        data_start = time.units.num2date(time.points[0])
        data_end = time.units.num2date(time.points[-1])

    if metadata['frequency'] in ['6hr', '3hr', '1hr',
                                 '6hrPt', '3hrPt', '1hrPt']:
        data_start = _round_time(data_start, 60)
        data_end = _round_time(data_end, 60)

    if file_start_date != data_start:
        msg = ('Start date in filename does not match the first time in the '
               'file ({}): {}'.format(str(data_start), metadata['basename']))
        raise FileValidationError(msg)
    elif file_end_date != data_end:
        msg = ('End date in filename does not match the last time in the '
               'file ({}): {}'.format(str(data_end), metadata['basename']))
        raise FileValidationError(msg)
    else:
        return True


def _round_time(dt=None, round_to=60):
    """
    Round a datetime object to any time lapse in seconds
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    From: https://stackoverflow.com/a/10854034

    :param datetime.datetime dt: The datetime to round
    :param int round_to: The closest number of seconds to round to, default
        one minute.
    """
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return dt + datetime.timedelta(0, rounding-seconds, -dt.microsecond)


def _check_contiguity(cube, metadata):
    """
    Check whether the time coordinate is contiguous

    :param iris.cube.Cube cube: The loaded file to check
    :param dict metadata: Metadata obtained from the file
    :returns: True if the data is contiguous
    :raises FileValidationError: If the data isn't contiguous
    """
    time_coord = cube.coord('time')

    time_point = False
    for cell_method in cube.cell_methods:
        if cell_method.method == 'point':
            time_point = True

    if time_point:
        # The time coordinate is points rather than a mean and so contiguity
        # errors won't show up with this method so pass the check.
        return True

    if time_coord.has_bounds():
        if not time_coord.is_contiguous():
            msg = ('The points in the time dimension in the file are not '
                   'contiguous: {}'.format(metadata['basename']))
            raise FileValidationError(msg)
        else:
            return True
    else:
        # The time coordinate has no bounds and so contiguity cannot be checked
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
        raise FileValidationError(msg)
    else:
        return True


def _check_cell_measure_point(cfreader, metadata):
    """
    Check if a data point can be read from a file containing a cell measure

    :param iris.fileformats.cf.CFReader cfreader: The CF metadata from the
        file
    :param dict metadata: Metadata obtained from the file
    :returns: True if a random point can be read from the file
    """
    cell_measure = None

    for cf_group in cfreader.cf_group.values():
        if cf_group.cf_name == metadata['cmor_name']:
            cell_measure = cf_group
            break

    if not cell_measure:
        msg = ('Unable to find cell measure in cfreader for variable {}'.
               format(metadata['cmor_name']))
        raise FileValidationError(msg)

    point_index = []
    for dim_length in cell_measure.cf_data.shape:
        point_index.append(random.randint(0, dim_length - 1))

    try:
        _data_point = cell_measure.cf_data[tuple(point_index)]
    except Exception:
        msg = 'Unable to extract data point {} from file: {}'.format(
            point_index, metadata['basename'])
        raise FileValidationError(msg)
    else:
        return True
