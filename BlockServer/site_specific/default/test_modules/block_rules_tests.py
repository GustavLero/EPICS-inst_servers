from server_common.mocks.mock_ca_server import MockCAServer
from BlockServer.site_specific.default.block_rules import BlockRules
import unittest
import json
import re
from server_common.utilities import dehex_and_decompress


class TestBlockRulesSequence(unittest.TestCase):
    """ Unit tests for block rules, note that changes here may have to be propagated to clients """

    def setUp(self):
        self.cas = MockCAServer()
        self.block_rules = BlockRules(self.cas)

    def get_block_rules_json(self):
        return json.loads(dehex_and_decompress(self.cas.pv_list.get("BLOCK_RULES")))

    def get_regex(self):
        regex_string = self.get_block_rules_json().get("regex")
        return re.compile(regex_string)

    def test_block_rules_pv(self):
        self.assertTrue("BLOCK_RULES" in self.cas.pv_list)

    def test_disallowed_in_json(self):
        self.assertTrue("disallowed" in self.get_block_rules_json())
        disallowed_list = self.get_block_rules_json().get("disallowed")
        self.assertTrue(isinstance(disallowed_list, list))

    def test_regex_in_json(self):
        self.assertTrue("regex" in self.get_block_rules_json())

    def test_regex_message_in_json(self):
        self.assertTrue("regex_message" in self.get_block_rules_json())

    def test_regex_lowercase_valid(self):
        self.assertTrue(self.get_regex().match("abc"))

    def test_regex_underscore_valid(self):
        self.assertTrue(self.get_regex().match("abc_"))

    def test_regex_uppercase_valid(self):
        regex = self.get_regex()
        self.assertTrue(regex.match("ABC"))

    def test_regex_numbers_valid(self):
        self.assertTrue(self.get_regex().match("abc1"))

    def test_regex_start_with_number_invalid(self):
        self.assertFalse(self.get_regex().match("1abc"))

    def test_regex_start_with_underscore_invalid(self):
        self.assertFalse(self.get_regex().match("_abc"))

    def test_regex_blank_invalid(self):
        self.assertFalse(self.get_regex().match(""))

    def test_regex_special_chars_invalid(self):
        self.assertFalse(self.get_regex().match("abc@"))