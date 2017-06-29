# This file is part of the ISIS IBEX application.
# Copyright (C) 2012-2016 Science & Technology Facilities Council.
# All rights reserved.
#
# This program is distributed in the hope that it will be useful.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License v1.0 which accompanies this distribution.
# EXCEPT AS EXPRESSLY SET FORTH IN THE ECLIPSE PUBLIC LICENSE V1.0, THE PROGRAM
# AND ACCOMPANYING MATERIALS ARE PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND.  See the Eclipse Public License v1.0 for more details.
#
# You should have received a copy of the Eclipse Public License v1.0
# along with this program; if not, you can obtain a copy from
# https://www.eclipse.org/org/documents/epl-v10.php or
# http://opensource.org/licenses/eclipse-1.0.php

import unittest
from datetime import datetime, timedelta

from hamcrest import *
from mock import Mock

from ArchiverAccess.archive_time_period import ArchiveTimePeriod
from ArchiverAccess.archiver_data_source import ArchiverDataSource, ArchiverDataValue, \
    VALUE_WHEN_ERROR_ON_RETRIEVAL
from server_common.mysql_abstraction_layer import DatabaseError


class SQLAbstractionStub(object):



    def __init__(self):
        self._initial_values_index = -1
        self.initial_values = []
        self.changes = []

    def add_initial_value(self, severity_id=None, status_id=None, num_val=None, float_val=None, str_val=None, array_val=None):
        archiver_data_value = ArchiverDataValue([severity_id, status_id, num_val, float_val, str_val, array_val])
        self.initial_values.append([archiver_data_value.get_as_array()])

    def add_changes(self, smpl_time, channel_name, severity_id=None, status_id=None, num_val=None, float_val=None, str_val=None, array_val=None):
        archiver_data_value = ArchiverDataValue([severity_id, status_id, num_val, float_val, str_val, array_val])
        change = [channel_name, smpl_time]
        change.extend(archiver_data_value.get_as_array())
        self.changes.append(change)

    def query(self, sql, param):
        self._initial_values_index += 1
        return self.initial_values[self._initial_values_index]

    def query_returning_cursor(self, sql, param):
        return self.changes


class TestArchiverDataSource(unittest.TestCase):

    def set_up_data_source(self):
        self.mysql_abstraction_layer = SQLAbstractionStub()
        self._data_source = ArchiverDataSource(self.mysql_abstraction_layer)

    def test_GIVEN_single_integer_pv_requested_WHEN_get_initial_values_THEN_value_returned(self):
        self.set_up_data_source()
        expected_value = 2
        self.mysql_abstraction_layer.add_initial_value(num_val=expected_value)

        result = self._data_source.initial_values(["a name"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([expected_value]))

    def test_GIVEN_single_float_pv_requested_WHEN_get_initial_values_THEN_value_returned(self):
        self.set_up_data_source()
        expected_value = 2.2
        self.mysql_abstraction_layer.add_initial_value(float_val=expected_value)

        result = self._data_source.initial_values(["a name"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([expected_value]))

    def test_GIVEN_single_string_pv_requested_WHEN_get_initial_values_THEN_value_returned(self):
        self.set_up_data_source()
        expected_value = "hi"
        self.mysql_abstraction_layer.add_initial_value(str_val=expected_value)

        result = self._data_source.initial_values(["a name"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([expected_value]))

    def test_GIVEN_no_results_for_pv_requested_WHEN_get_initial_values_THEN_None_value_returned(self):
        self.set_up_data_source()

        self.mysql_abstraction_layer.initial_values = [[]]

        result = self._data_source.initial_values(["a name"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([None]))

    def test_GIVEN_too_many_results_for_pv_requested_WHEN_get_initial_values_THEN_exception_thrown(self):
        self.set_up_data_source()

        self.mysql_abstraction_layer.add_initial_value()
        self.mysql_abstraction_layer.initial_values[0].append(self.mysql_abstraction_layer.initial_values[0])

        result = self._data_source.initial_values(["a name"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([VALUE_WHEN_ERROR_ON_RETRIEVAL]))

    def test_GIVEN_results_for_multiple_pvs_requested_WHEN_get_initial_values_THEN_values_returned(self):
        self.set_up_data_source()
        expected_value1 = 2.2
        self.mysql_abstraction_layer.add_initial_value(float_val=expected_value1)
        expected_value2 = 4
        self.mysql_abstraction_layer.add_initial_value(num_val=expected_value2)

        result = self._data_source.initial_values(["pv one", "pv name two"], datetime(2017, 1, 2, 3, 4, 5))

        assert_that(result, is_([expected_value1, expected_value2]))

    def test_GIVEN_single_integer_pv_requested_WHEN_get_changes_generator_values_THEN_value_returned(self):
        channel_name = "channel name"
        self.set_up_data_source()
        expected_value = 2.1
        expected_time_stamp = datetime(2010, 9, 8, 2, 3, 4)
        self.mysql_abstraction_layer.add_changes(smpl_time=expected_time_stamp, float_val=expected_value, channel_name=channel_name)

        changes = []
        for change in self._data_source.changes_generator((channel_name,), ArchiveTimePeriod(datetime(2017, 1, 2, 3, 4, 5), timedelta(seconds=1), 10)):
            changes.append(change)

        assert_that(changes, is_([(expected_time_stamp, 0, expected_value)]))

    def test_GIVEN_multiple_pvs_requested_WHEN_get_changes_generator_values_THEN_values_returned(self):
        channel_name = "channel name"

        expected_value = "hi"
        expected_time_stamp = datetime(2010, 9, 8, 2, 3, 4)

        channel_name2 = "channel name2"
        expected_value2 = 6
        expected_time_stamp2 = datetime(2010, 9, 8, 2, 4, 5)
        self.set_up_data_source()
        self.mysql_abstraction_layer.add_changes(smpl_time=expected_time_stamp, str_val=expected_value, channel_name=channel_name)
        self.mysql_abstraction_layer.add_changes(smpl_time=expected_time_stamp2, num_val=expected_value2,
                                                 channel_name=channel_name2)

        changes = []
        for change in self._data_source.changes_generator((channel_name, channel_name2),  ArchiveTimePeriod(datetime(2017, 1, 2, 3, 4, 5), timedelta(seconds=1), 10)):
            changes.append(change)

        assert_that(changes, is_([(expected_time_stamp, 0, expected_value),
                                  (expected_time_stamp2, 1, expected_value2)]))

    def test_GIVEN_no_results_for_multiple_pvs_requested_WHEN_get_changes_THEN_blank_list_returned(self):
        channel_name = "channel name"
        channel_name2 = "channel name2"
        self.set_up_data_source()

        changes = []
        for change in self._data_source.changes_generator((channel_name, channel_name2), ArchiveTimePeriod(datetime(2017, 1, 2, 3, 4, 5), timedelta(seconds=1), 10)):
            changes.append(change)

        assert_that(changes, is_(empty()))

    def test_GIVEN_querry_gives_error_WHEN_get_changes_generator_values_THEN_error(self):
        channel_name = "channel name"
        self.set_up_data_source()
        self.mysql_abstraction_layer.query_returning_cursor = Mock(side_effect=DatabaseError("Problems with accessing the database"))

        gen = self._data_source.changes_generator((channel_name,), ArchiveTimePeriod(datetime(2017, 1, 2, 3, 4, 5), timedelta(seconds=1), 10))

        assert_that(calling(gen.next), raises(DatabaseError))
