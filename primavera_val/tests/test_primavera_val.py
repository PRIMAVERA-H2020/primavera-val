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

from primavera_val import (identify_filename_metadata, _check_contiguity,
                           _check_start_end_times, FileValidationError)

class TestIdentifyFilenameMetadata(unittest.TestCase):
    @mock.patch('primavera_val.os.path.getsize')
    def setUp(self, mock_getsize):
        mock_getsize.return_value = 1234

        filename_5 = 'clt_Amon_Monty_historical_r1i1p1_185912-188411.nc'

        self.metadata_5 = identify_filename_metadata(filename_5,
                                                     file_format='CMIP5')

        filename_6 = ('prc_day_highres-future_HadGEM3_r1i1p1f1_gn_'
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
            identify_filename_metadata, filename, file_format='CMIP5')

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
            identify_filename_metadata, filename, file_format='CMIP6')


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


if __name__ == '__main__':
    unittest.main()