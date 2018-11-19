# (C) British Crown Copyright 2017, Met Office.
# Please see LICENSE.rst for license details.
# pylint: disable = missing-docstring, invalid-name, too-many-public-methods
"""
Tests for primavera_val.
"""
from __future__ import unicode_literals, division, absolute_import
import datetime
import mock
import six
import unittest

import iris
from iris.time import PartialDateTime
from iris.tests.stock import realistic_3d

from primavera_val import (identify_filename_metadata, _get_frequency,
                           identify_contents_metadata, _check_contiguity,
                           _check_start_end_times, _round_time,
                           FileValidationError)


class TestIdentifyFilenameMetadata(unittest.TestCase):
    @mock.patch('primavera_val.os.path.getsize')
    def setUp(self, mock_getsize):
        mock_getsize.return_value = 1234

        filename_5 = 'clt_Amon_Monty_historical_r1i1p1_185912-188411.nc'

        self.metadata_5 = identify_filename_metadata(filename_5,
                                                     file_format='CMIP5')

        filename_6 = ('prc_day_HadGEM3_highres-future_r1i1p1f1_gn_'
                      '19500101-19501230.nc')

        self.metadata_6 = identify_filename_metadata(filename_6,
                                                     file_format='CMIP6')

        filename_6_clim = ('phalf_Amon_HadGEM3-GC31-LM_highresSST-present_'
                           'r1i1p1f1_gn_195001-195101-clim.nc')

        self.metadata_6_clim = identify_filename_metadata(filename_6_clim,
                                                          file_format='CMIP6')

    def test_cmor_name(self):
        self.assertEqual(self.metadata_5['cmor_name'], 'clt')

    def test_table(self):
        self.assertEqual(self.metadata_5['table'], 'Amon')

    def test_climate_model(self):
        self.assertEqual(self.metadata_5['climate_model'], 'Monty')

    def test_experiment(self):
        self.assertEqual(self.metadata_5['experiment'], 'historical')

    def test_rip_code(self):
        self.assertEqual(self.metadata_5['rip_code'], 'r1i1p1')

    def test_start_date(self):
        self.assertEqual(self.metadata_5['start_date'],
                         PartialDateTime(year=1859, month=12))

    def test_end_date(self):
        self.assertEqual(self.metadata_5['end_date'],
                         PartialDateTime(year=1884, month=11))

    def test_bad_date_format(self):
        filename = 'clt_Amon_Monty_historical_r1i1p1_1859-1884.nc'
        self.assertRaises(FileValidationError,
                          identify_filename_metadata, filename,
                          file_format='CMIP5')

    def test_cmor_name_6(self):
        self.assertEqual(self.metadata_6['cmor_name'], 'prc')

    def test_table_6(self):
        self.assertEqual(self.metadata_6['table'], 'day')

    def test_climate_model_6(self):
        self.assertEqual(self.metadata_6['climate_model'], 'HadGEM3')

    def test_experiment_6(self):
        self.assertEqual(self.metadata_6['experiment'], 'highres-future')

    def test_rip_code_6(self):
        self.assertEqual(self.metadata_6['rip_code'], 'r1i1p1f1')

    def test_grid_6(self):
        self.assertEqual(self.metadata_6['grid'], 'gn')

    def test_start_date_6(self):
        self.assertEqual(self.metadata_6['start_date'],
                         PartialDateTime(year=1950, month=1, day=1))

    def test_end_date_6(self):
        self.assertEqual(self.metadata_6['end_date'],
                         PartialDateTime(year=1950, month=12, day=30))

    def test_end_date_6_climatology(self):
        self.assertEqual(self.metadata_6_clim['end_date'],
                         PartialDateTime(year=1951, month=1))

    def test_bad_date_format_6(self):
        filename = 'prc_day_highres-future_HadGEM3_r1i1p1f1_gn_1950-1950.nc'
        self.assertRaises(FileValidationError,
                          identify_filename_metadata, filename,
                          file_format='CMIP6')


class TestIdentifyContentsMetadata(unittest.TestCase):
    def setUp(self):
        self.cube = realistic_3d()
        self.cube.attributes['institution_id'] = 'ABCD'

        self.expected = {'var_name': None, 'units': 'K', 'long_name': None,
                         'standard_name': 'air_potential_temperature',
                         'time_units': 'hours since 1970-01-01 00:00:00',
                         'calendar': 'gregorian', 'activity_id': 'HighResMIP',
                         'institute': 'ABCD'}

    def test_default_activity(self):
        actual = identify_contents_metadata(self.cube, 'abc.nc')
        self.assertEqual(actual, self.expected)

    def test_custom_activity(self):
        self.cube.attributes['activity_id'] = 'ZYXW'
        self.expected['activity_id'] = 'ZYXW'

        actual = identify_contents_metadata(self.cube, 'abc.nc')
        self.assertEqual(actual, self.expected)

    def test_cmip5_institute(self):
        del self.cube.attributes['institution_id']
        self.cube.attributes['institute_id'] = 'EFGH'
        self.expected['institute'] = 'EFGH'

        actual = identify_contents_metadata(self.cube, 'abc.nc')
        self.assertEqual(actual, self.expected)

    def test_exception_raised(self):
        del self.cube.attributes['institution_id']

        six.assertRaisesRegex(
            self,
            FileValidationError,
            "Unable to extract metadata from the contents of file abc.nc.*",
            identify_contents_metadata,
            self.cube,
            'abc.nc'
        )


class TestCheckStartEndTimes(unittest.TestCase):
    def setUp(self):
        self.cube = realistic_3d()

        self.metadata_1 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=12),
                           'end_date': PartialDateTime(year=2014, month=12),
                           'frequency': 'mon'}
        self.metadata_2 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=11),
                           'end_date': PartialDateTime(year=2014, month=12),
                           'frequency': 'mon'}
        self.metadata_3 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2013, month=12),
                           'end_date': PartialDateTime(year=2014, month=12),
                           'frequency': 'mon'}
        self.metadata_4 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=12),
                           'end_date': PartialDateTime(year=2015, month=9),
                           'frequency': 'mon'}
        self.metadata_5 = {'basename': 'file-clim.nc',
                           'start_date': PartialDateTime(year=2014, month=12,
                                                         day=20),
                           'end_date': PartialDateTime(year=2014, month=12,
                                                       day=22),
                           'frequency': 'mon'}
        self.metadata_6 = {'basename': 'file-clim.nc',
                           'start_date': PartialDateTime(year=2014, month=12,
                                                         day=21),
                           'end_date': PartialDateTime(year=2014, month=12,
                                                       day=22),
                           'frequency': 'mon'}
        self.metadata_high_freq = {
            'basename': 'file.nc',
            'start_date': PartialDateTime(year=2014, month=12, day=21,
                                          hour=0, minute=0),
            'end_date': PartialDateTime(year=2014, month=12, day=22,
                                        hour=12, minute=0),
            'frequency': '6hr'}

    def test_equals(self):
        self.assertTrue(_check_start_end_times(self.cube, self.metadata_1))

    def test_fails_start_month(self):
        self.assertRaises(FileValidationError, _check_start_end_times,
                          self.cube, self.metadata_2)

    def test_fails_start_year(self):
        self.assertRaises(FileValidationError, _check_start_end_times,
                          self.cube, self.metadata_3)

    def test_fails_end(self):
        self.assertRaises(FileValidationError, _check_start_end_times,
                          self.cube, self.metadata_4)

    def test_climatology_passes(self):
        self.cube.coord('time').guess_bounds()
        self.assertTrue(_check_start_end_times(self.cube, self.metadata_5))

    def test_climatology_fails(self):
        self.cube.coord('time').guess_bounds()
        self.assertRaises(FileValidationError, _check_start_end_times,
                          self.cube, self.metadata_6)

    def test_high_freq(self):
        self.assertTrue(_check_start_end_times(self.cube,
                                               self.metadata_high_freq))

    def test_high_freq_rounded_fails(self):
        time_coord = self.cube.coord('time')
        time_coord_points = time_coord.points.copy()
        time_coord_points[-1] += 34 / 60**2
        time_coord.points = time_coord_points
        self.assertRaises(FileValidationError, _check_start_end_times,
                          self.cube, self.metadata_high_freq)

    def test_high_freq_rounded(self):
        self.metadata_high_freq['end_date'] = PartialDateTime(
            year=2014,
            month=12,
            day=22,
            hour=12,
            minute=1
        )
        time_coord = self.cube.coord('time')
        time_coord_points = time_coord.points.copy()
        time_coord_points[-1] += 34 / 60**2
        time_coord.points = time_coord_points
        self.assertTrue(_check_start_end_times(self.cube,
                                               self.metadata_high_freq))


class TestCheckContiguity(unittest.TestCase):
    def setUp(self):
        self.good_cube = realistic_3d()
        self.good_cube.coord('time').guess_bounds()

        cubes = iris.cube.CubeList([self.good_cube[:2], self.good_cube[4:]])
        self.bad_cube = cubes.concatenate_cube()

    def test_contiguous(self):
        self.assertTrue(
            _check_contiguity(self.good_cube, {'basename': 'file.nc'}))

    def test_not_contiguous(self):
        self.assertRaises(FileValidationError, _check_contiguity,
                          self.bad_cube, {'basename': 'file.nc'})

    def test_time_point(self):
        self.bad_cube.cell_methods = self.bad_cube.cell_methods + (
            iris.coords.CellMethod('point', coords=('time',)),
        )

        self.assertTrue(
            _check_contiguity(self.bad_cube, {'basename': 'file.nc'}))


class TestRoundTime(unittest.TestCase):
    def test_minute_down(self):
        input_time = datetime.datetime(2018, 11, 19, 12, 29, 22)
        output_time = _round_time(input_time)
        self.assertEqual(output_time,
                         datetime.datetime(2018, 11, 19, 12, 29))

    def test_minute_up(self):
        input_time = datetime.datetime(2018, 11, 19, 12, 29, 32)
        output_time = _round_time(input_time)
        self.assertEqual(output_time,
                         datetime.datetime(2018, 11, 19, 12, 30))

    def test_nothing_required(self):
        input_time = datetime.datetime(2018, 11, 19, 12, 29)
        output_time = _round_time(input_time)
        self.assertEqual(output_time,
                         datetime.datetime(2018, 11, 19, 12, 29))

    def test_hour_down(self):
        input_time = datetime.datetime(2018, 11, 19, 12, 29, 22)
        output_time = _round_time(input_time, 60**2)
        self.assertEqual(output_time,
                         datetime.datetime(2018, 11, 19, 12, 00))


class TestGetFrequency(unittest.TestCase):
    def setUp(self):
        self.mip_tables = {
            '3hr': '3hr',
            '6hrLev': '6hr',
            '6hrPlev': '6hr',
            '6hrPlevPt': '6hr',
            'AERday': 'day',
            'AERfx': 'fx',
            'AERhr': 'hr',
            'AERmon': 'mon',
            'AERmonZ': 'mon',
            'Amon': 'mon',
            'CF3hr': '3hr',
            'CFday': 'day',
            'CFmon': 'mon',
            'CFsubhr': 'subhr',
            'CFsubhrOff': 'subhr',
            'E1hr': '1hr',
            'E1hrClimMon': '1hr',
            'E3hr': '3hr',
            'E3hrPt': '3hr',
            'E6hrZ': '6hr',
            'Eday': 'day',
            'EdayZ': 'day',
            'Efx': 'fx',
            'Emon': 'mon',
            'EmonZ': 'mon',
            'Esubhr': 'subhr',
            'Eyr': 'yr',
            'IfxAnt': 'fx',
            'IfxGre': 'fx',
            'ImonAnt': 'mon',
            'ImonGre': 'mon',
            'IyrAnt': 'yr',
            'IyrGre': 'yr',
            'LImon': 'mon',
            'Lmon': 'mon',
            'Oclim': 'clim',
            'Oday': 'day',
            'Odec': 'dec',
            'Ofx': 'fx',
            'Omon': 'mon',
            'Oyr': 'yr',
            'aero': 'aero',
            'cfOff': 'cf',
            'cfSites': 'cf',
            'Prim1hr': '1hr',
            'Prim3hr': '3hr',
            'Prim3hrPt': '3hr',
            'Prim6hr': '6hr',
            'Prim6hrPt': '6hr',
            'Primday': 'day',
            'Primmon': 'mon',
            'PrimO6hr': '6hr',
            'PrimOday': 'day',
            'PrimOmon': 'mon',
            'PrimSIday': 'day',
            'PrimmonZ': 'mon',
            'PrimdayPt': 'day',
            'SIday': 'day',
            'SImon': 'mon',
            'day': 'day',
            'fx': 'fx',
            'grids': 'grids'
        }

    def test_all_table_names(self):
        for mip_table in self.mip_tables:
            self.assertEqual(_get_frequency(mip_table),
                             self.mip_tables[mip_table])


if __name__ == '__main__':
    unittest.main()
