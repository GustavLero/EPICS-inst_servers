import collections


period_data_point = collections.namedtuple("period_data_point", "time values")
"""a single periodic data point, essential all the values at a point in time"""


class PeriodicDataGenerator(object):
    """
    Generate the data as a set of periodic values.

    This changes the form of the data from the archiver_data from points in time when PVs changed to regular pv values.
    This snaps shots the value at the point of time required.
    """

    def __init__(self, archiver_data_source):
        """
        Constructor

        Args:
            archiver_data_source(ArchiverAccess.archiver_data_source.ArchiverDataSource): data source for archive data
        """
        self._archiver_data_source = archiver_data_source

    def get_generator(self, pv_names, time_period):
        """
        Get a generator which produces data points.

        Args:
            pv_names: list of relevant pv names for periodic data
            time_period(ArchiverAccess.archive_time_period.ArchiveTimePeriod): time period over which the periodic data
            should be generated

        :return: Generator for a data point which is a period_data_point tuple
        """

        archiver_changes_generator = self._archiver_data_source.changes_generator(pv_names, time_period)
        current_values = self._archiver_data_source.initial_values(pv_names, time_period.start_time)
        self._set_next_change(archiver_changes_generator)

        for current_point_count in range(time_period.point_count + 1):
            current_time = time_period.get_time_after(current_point_count)
            current_values = self._get_values_at_time(current_values, current_time, archiver_changes_generator)

            yield period_data_point(current_time, current_values)

    def _get_values_at_time(self, initial_values, time, _archiver_changes_generator):
        """
        Get the values for the given time by iterating through the changes in the values until the current change
        is after the needed change and updating the current values as we go.
        :param initial_values: the initial values
        :param time: the time that we want the values for
        :return: list of values at the wanted time
        """
        updated_list = list(initial_values)
        while self._next_change_time is not None and self._next_change_time <= time:
            updated_list[self._next_change_index] = self._next_change_value
            self._set_next_change(_archiver_changes_generator)

        return updated_list

    def _set_next_change(self, _archiver_changes_generator):
        """
        Get the next change in the change list
        :return:
        """
        try:
            self._next_change_time, self._next_change_index, self._next_change_value = \
                _archiver_changes_generator.next()
        except StopIteration:
            self._next_change_time = None
