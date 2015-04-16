import unittest
from BlockServer.core.ioc_control import IocControl, IOCS_NOT_TO_STOP
from BlockServer.mocks.mock_procserv_utils import MockProcServWrapper


class TestIocControlSequence(unittest.TestCase):
    def test_start_ioc_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_ioc("TESTIOC")
        self.assertEqual(ic.get_ioc_status("TESTIOC"), "RUNNING")

    def test_stop_ioc_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_ioc("TESTIOC")
        ic.stop_ioc("TESTIOC")
        self.assertEqual(ic.get_ioc_status("TESTIOC"), "SHUTDOWN")

    def test_restart_ioc_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_ioc("TESTIOC")
        ic.restart_ioc("TESTIOC")
        self.assertEqual(ic.get_ioc_status("TESTIOC"), "RUNNING")

    def test_stop_ioc_on_not_allowed_to_stop(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_ioc(IOCS_NOT_TO_STOP[0])
        ic.stop_ioc(IOCS_NOT_TO_STOP[0])
        self.assertEqual(ic.get_ioc_status(IOCS_NOT_TO_STOP[0]), "RUNNING")

    def test_restart_ioc_on_not_allowed_to_stop(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_ioc(IOCS_NOT_TO_STOP[0])
        ic.restart_ioc(IOCS_NOT_TO_STOP[0])
        self.assertEqual(ic.get_ioc_status(IOCS_NOT_TO_STOP[0]), "RUNNING")

    def test_start_iocs_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_iocs(["TESTIOC1", "TESTIOC2"])
        self.assertEqual(ic.get_ioc_status("TESTIOC1"), "RUNNING")
        self.assertEqual(ic.get_ioc_status("TESTIOC2"), "RUNNING")

    def test_stop_iocs_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_iocs(["TESTIOC1", "TESTIOC2"])
        ic.stop_iocs(["TESTIOC1", "TESTIOC2"])
        self.assertEqual(ic.get_ioc_status("TESTIOC1"), "SHUTDOWN")
        self.assertEqual(ic.get_ioc_status("TESTIOC2"), "SHUTDOWN")

    def test_restart_iocs_and_get_ioc_status(self):
        ic = IocControl("", MockProcServWrapper())
        ic.start_iocs(["TESTIOC1", "TESTIOC2"])
        ic.restart_iocs(["TESTIOC1", "TESTIOC2"])
        self.assertEqual(ic.get_ioc_status("TESTIOC1"), "RUNNING")
        self.assertEqual(ic.get_ioc_status("TESTIOC2"), "RUNNING")

    def test_ioc_exists(self):
        ic = IocControl("", MockProcServWrapper())
        self.assertTrue(ic.ioc_exists("TESTIOC"))