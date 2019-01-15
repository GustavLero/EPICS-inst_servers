"""
Make channel access not dependent on genie_python.
"""
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
from enum import Enum

from server_common.utilities import print_and_log
import threading
try:
    from genie_python.channel_access_exceptions import UnableToConnectToPVException
except ImportError:
    class UnableToConnectToPVException(IOError):
        """
        The system is unable to connect to a PV for some reason.
        """
        def __init__(self, pv_name, err):
            super(UnableToConnectToPVException, self).__init__("Unable to connect to PV {0}: {1}".format(pv_name, err))


class AlarmSeverity(Enum):
    """
    Enum for severity of alarm
    """
    NoAlarm = 0
    Minor = 1
    Major = 2
    invalid = 3

    @staticmethod
    def from_ca_channel(severity):
        """
        Convert from a ca channel severity.
        Isolates code from CaChannel internal.
        Args:
            severity (CaChannel._ca.AlarmSeverity): ca channel severity
        Returns: severity

        """
        # noinspection PyTypeChecker
        for alarm_severity in AlarmSeverity:
            if alarm_severity.value == severity.value:
                return alarm_severity


class AlarmStatus(Enum):
    """
    Enum for status of alarm
    """
    BadSub = 16
    Calc = 12
    Comm = 9
    Cos = 8
    Disable = 18
    High = 4
    HiHi = 3
    HwLimit = 11
    Link = 14
    Lolo = 5
    Low = 6
    NoAlarm = 0
    Read = 1
    ReadAccess = 20
    Scam = 13
    Simm = 19
    Soft = 15
    State = 7
    Timeout = 10
    UDF = 17
    Write = 2
    WriteAccess = 21

    @staticmethod
    def from_ca_channel(status):
        """
        Convert from a ca channel status.
        Isolates code from CaChannel internal.
        Args:
            status (CaChannel._ca.AlarmStatus): ca channel status
        Returns: severity

        """
        # noinspection PyTypeChecker
        for alarm_status in AlarmStatus:
            if alarm_status == status.value:
                return alarm_status


class ChannelAccess(object):
    """
    Channel access methods. Items from genie_python are imported locally so that this module can be imported without
    installing genie_python.
    """
    @staticmethod
    def caget(name, as_string=False):
        """Uses CaChannelWrapper from genie_python to get a pv value. We import CaChannelWrapper when used as this means
        the tests can run without having genie_python installed

        Args:
            name (string): The name of the PV to be read
            as_string (bool, optional): Set to read a char array as a string, defaults to false

        Returns:
            obj : The value of the requested PV, None if no value was read
        """

        from genie_python.genie_cachannel_wrapper import CaChannelWrapper
        try:
            return CaChannelWrapper.get_pv_value(name, as_string)
        except Exception as err:
            # Probably has timed out
            print_and_log(str(err))
            return None

    @staticmethod
    def caput(name, value, wait=False):
        """Uses CaChannelWrapper from genie_python to set a pv value. We import CaChannelWrapper when used as this means
        the tests can run without having genie_python installed

        Args:
            name (string): The name of the PV to be set
            value (object): The data to send to the PV
            wait (bool, optional): Wait for the PV t set before returning
        """
        def _put_value():
            from genie_python.genie_cachannel_wrapper import CaChannelWrapper
            CaChannelWrapper.set_pv_value(name, value, wait)

        if wait:
            # If waiting then run in this thread.
            _put_value()
        else:
            # If not waiting, run in a different thread.
            # Even if not waiting genie_python sometimes takes a while to return from a set_pv_value call.
            thread = threading.Thread(target=_put_value)
            thread.start()

    @staticmethod
    def pv_exists(name, timeout=None):
        """
        See if the PV exists.

        Args:
            name (string): The PV name.
            timeout(optional): How long to wait for the PV to "appear".

        Returns:
            True if exists, otherwise False.
        """
        from genie_python.genie_cachannel_wrapper import CaChannelWrapper, EXIST_TIMEOUT
        if timeout is None:
            timeout = EXIST_TIMEOUT
        return CaChannelWrapper.pv_exists(name, timeout)

    @staticmethod
    def add_monitor(name, call_back_function):
        """
        Add a callback to a pv which responds on a monitor (i.e. value change). This currently only tested for
        numbers.
        Args:
            name: name of the pv
            call_back_function: the callback function, arguments are value,
                alarm severity (AlarmSeverity),
                alarm status (AlarmStatus)
        """
        from genie_python.genie_cachannel_wrapper import CaChannelWrapper

        def _intermediate_callback(value, severity, status):
            call_back_function(value, AlarmSeverity.from_ca_channel(severity), AlarmStatus.from_ca_channel(status))
        CaChannelWrapper.add_monitor(name, _intermediate_callback)

    @staticmethod
    def poll():
        """
        Flush the send buffer and execute any outstanding background activity for all connected pvs.
        NB Connected pv is one which is in the cache
        """
        from genie_python.genie_cachannel_wrapper import CaChannelWrapper
        CaChannelWrapper.poll()
