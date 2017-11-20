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
from __future__ import absolute_import
import os

# Set MYPVPREFIX env var
os.environ['MYPVPREFIX'] = ""

from BlockServer.runcontrol.runcontrol_manager import RunControlManager, RC_START_PV
from BlockServer.mocks.mock_block_server import MockBlockServer
from BlockServer.mocks.mock_ioc_control import MockIocControl
from BlockServer.mocks.mock_channel_access import MockChannelAccess, PVS, ChannelAccessEnv
from BlockServer.mocks.mock_active_config_holder import MockActiveConfigHolder
from BlockServer.config.configuration import Configuration
from BlockServer.mocks.mock_version_control import MockVersionControl
from BlockServer.mocks.mock_ioc_control import MockIocControl
from BlockServer.mocks.mock_archiver_wrapper import MockArchiverWrapper
from BlockServer.epics.archiver_manager import ArchiverManager
from BlockServer.core.file_path_manager import FILEPATH_MANAGER
import unittest
from datetime import datetime, timedelta


MACROS = {
    "$(MYPVPREFIX)": os.environ['MYPVPREFIX']
}


# Helper methods
def quick_block_to_json(name, pv, group, local=True):
    data = {'name': name, 'pv': pv, 'group': group, 'local': local}
    return data


def add_block(cs, data):
    cs.add_block(data)


def dummy_sleep_func(seconds):
    return


def _get_relative_time(t, **kwargs):
    return datetime.strftime(t + timedelta(**kwargs), '%m/%d/%Y %H:%M:%S')


def _get_current_time():
    return datetime.strftime(datetime.now(), '%m/%d/%Y %H:%M:%S')


class TestRunControlSequence(unittest.TestCase):
    def setUp(self):
        self.activech = MockActiveConfigHolder(MACROS)
        self.cs = MockChannelAccess()
        self.set_start_time_of_run_control()
        self.rcm = RunControlManager("", "", "", MockIocControl(""), self.activech, MockBlockServer(), self.cs,
                                     dummy_sleep_func)

    def set_start_time_of_run_control(self, start_time=_get_current_time()):
        PVS[MACROS["$(MYPVPREFIX)"] + RC_START_PV] = start_time

    def test_get_runcontrol_settings_empty(self):
        self.set_start_time_of_run_control()
        self.rcm.create_runcontrol_pvs(False, 0)
        ans = self.rcm.get_current_settings()
        self.assertTrue(len(ans) == 0)

    def test_get_runcontrol_settings_blocks(self):
        add_block(self.activech, quick_block_to_json(
            "TESTBLOCK1", "PV1", "GROUP1", True))
        add_block(self.activech, quick_block_to_json(
            "TESTBLOCK2", "PV2", "GROUP2", True))
        add_block(self.activech, quick_block_to_json(
            "TESTBLOCK3", "PV3", "GROUP2", True))
        add_block(self.activech, quick_block_to_json(
            "TESTBLOCK4", "PV4", "NONE", True))
        self.set_start_time_of_run_control()
        self.rcm.create_runcontrol_pvs(False, 0)
        ans = self.rcm.get_current_settings()
        self.assertTrue(len(ans) == 4)
        self.assertTrue("HIGH" in ans["TESTBLOCK1"])
        self.assertTrue("LOW" in ans["TESTBLOCK1"])
        self.assertTrue("ENABLE" in ans["TESTBLOCK1"])
        self.assertTrue("HIGH" in ans["TESTBLOCK2"])
        self.assertTrue("LOW" in ans["TESTBLOCK2"])
        self.assertTrue("ENABLE" in ans["TESTBLOCK2"])
        self.assertTrue("HIGH" in ans["TESTBLOCK3"])
        self.assertTrue("LOW" in ans["TESTBLOCK3"])
        self.assertTrue("ENABLE" in ans["TESTBLOCK3"])
        self.assertTrue("HIGH" in ans["TESTBLOCK4"])
        self.assertTrue("LOW" in ans["TESTBLOCK4"])
        self.assertTrue("ENABLE" in ans["TESTBLOCK4"])

    def test_get_runcontrol_settings_blocks_limits(self):
        data = {'name': "TESTBLOCK1", 'pv': "PV1",
                'runcontrol': True, 'lowlimit': -5, 'highlimit': 5}
        add_block(self.activech, data)
        self.set_start_time_of_run_control()
        self.rcm.create_runcontrol_pvs(False, 0)
        ans = self.rcm.get_current_settings()
        self.assertTrue(len(ans) == 1)
        self.assertTrue(ans["TESTBLOCK1"]["HIGH"] == 5)
        self.assertTrue(ans["TESTBLOCK1"]["LOW"] == -5)

    def test_set_runcontrol_settings_limits(self):
        data = {'name': "TESTBLOCK1", 'pv': "PV1",
                'runcontrol': True, 'lowlimit': -5, 'highlimit': 5}
        add_block(self.activech, data)
        self.set_start_time_of_run_control()
        self.rcm.create_runcontrol_pvs(False, 0)
        ans = self.rcm.get_current_settings()
        ans["TESTBLOCK1"]["LOW"] = 0
        ans["TESTBLOCK1"]["HIGH"] = 10
        ans["TESTBLOCK1"]["ENABLE"] = False
        self.rcm.set_runcontrol_settings(ans)
        ans = self.rcm.get_current_settings()
        self.assertEqual(ans["TESTBLOCK1"]["HIGH"], 10)
        self.assertEqual(ans["TESTBLOCK1"]["LOW"], 0)

    def test_GIVEN_non_restarting_runcontrol_WHEN_create_PVs_THAT_code_is_not_stuck_in_loop(self):
        prefix = ""
        rc_pv = prefix + RC_START_PV

        now = datetime.now()
        with ChannelAccessEnv({rc_pv: [_get_relative_time(now, minutes=-3)]}) as channel:
            rcm = RunControlManager(prefix, "", "",
                                    MockIocControl(""), self.activech,
                                    MockBlockServer(), self.cs, dummy_sleep_func)
            self.assertEqual(channel.get_call_count(rc_pv), 1)

    def test_GIVEN_already_started_runcontrol_WHEN_restart_THAT_code_is_not_stuck_in_loop(self):
        prefix = ""
        rc_pv = prefix + RC_START_PV

        now = datetime.now()
        env = {rc_pv: [_get_relative_time(now, minutes=-3), "", _get_relative_time(now, minutes=-2)]}
        with ChannelAccessEnv(env) as channel:
            rcm = RunControlManager(prefix, "", "",
                                    MockIocControl(""), self.activech,
                                    MockBlockServer(), self.cs, dummy_sleep_func)
            rcm.create_runcontrol_pvs(False, 0)
            self.assertEqual(channel.get_call_count(rc_pv), 3)

    def test_GIVEN_nonsense_runcontrol_start_time_WHEN_restart_runcontrol_THAT_code_loops_to_restart_runcontrol(self):
        prefix = ""
        rc_pv = "" + RC_START_PV
        with ChannelAccessEnv({rc_pv: [""] * 60}) as channel:
            rcm = RunControlManager(prefix, "", "",
                                    MockIocControl(""), self.activech,
                                    MockBlockServer(), self.cs, dummy_sleep_func)
            self.assertEqual(channel.get_call_count(rc_pv), 60)
