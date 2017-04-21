# (C) British Crown Copyright 2017, Met Office.
# Please see LICENSE.rst for license details.
# pylint: disable = missing-docstring, invalid-name, too-many-public-methods
"""
Tests for primavera_val.
"""
import unittest
import mock

import iris
from iris.time import PartialDateTime
from iris.tests.stock import realistic_3d

from primavera_val import (identify_filename_metadata, _get_frequency,
                           identify_contents_metadata, _check_contiguity,
                           _check_start_end_times, FileValidationError)


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

    @mock.patch('primavera_val.logger')
    def test_bad_date_format(self, mock_logger):
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
                         PartialDateTime(year=1950, month=01, day=01))

    def test_end_date_6(self):
        self.assertEqual(self.metadata_6['end_date'],
                         PartialDateTime(year=1950, month=12, day=30))

    @mock.patch('primavera_val.logger')
    def test_bad_date_format_6(self, mock_logger):
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

    @mock.patch('primavera_val.logger')
    def test_exception_raised(self, mock_logger):
        del self.cube.attributes['institution_id']

        self.assertRaisesRegexp(
            FileValidationError,
            'Unable to extract metadata from the contents of file abc.nc\n'
            'institute_id',
            identify_contents_metadata,
            self.cube,
            'abc.nc'
        )


class TestCheckStartEndTimes(unittest.TestCase):
    def setUp(self):
        self.cube = realistic_3d()

        self.metadata_1 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=12),
                           'end_date': PartialDateTime(year=2014, month=12)}
        self.metadata_2 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=11),
                           'end_date': PartialDateTime(year=2014, month=12)}
        self.metadata_3 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2013, month=12),
                           'end_date': PartialDateTime(year=2014, month=12)}
        self.metadata_4 = {'basename': 'file.nc',
                           'start_date': PartialDateTime(year=2014, month=12),
                           'end_date': PartialDateTime(year=2015, month=9)}

        # mock logger to prevent it displaying messages on screen
        patch = mock.patch('primavera_val.logger')
        self.mock_logger = patch.start()
        self.addCleanup(patch.stop)

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


class TestCheckContiguity(unittest.TestCase):
    def setUp(self):
        # mock logger to prevent it displaying messages on screen
        patch = mock.patch('primavera_val.logger')
        self.mock_logger = patch.start()
        self.addCleanup(patch.stop)

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


class TestCheckDataPoint(unittest.TestCase):
    def test_todo(self):
        # TODO: figure put how to test this function
        pass


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
