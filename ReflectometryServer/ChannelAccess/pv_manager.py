"""
Reflectometry pv manager
"""
from enum import Enum

from ReflectometryServer.parameters import BeamlineParameterType
from server_common.ioc_data_source import PV_INFO_FIELD_NAME, PV_DESCRIPTION_NAME
from server_common.utilities import create_pv_name, remove_from_end, print_and_log, SEVERITY, compress_and_hex
import json
from collections import OrderedDict


PARAM_PREFIX = "PARAM"
BEAMLINE_PREFIX = "BL:"
BEAMLINE_MODE = BEAMLINE_PREFIX + "MODE"
BEAMLINE_MOVE = BEAMLINE_PREFIX + "MOVE"
BEAMLINE_STATUS = BEAMLINE_PREFIX + "STAT"
BEAMLINE_MESSAGE = BEAMLINE_PREFIX + "MSG"
PARAM_INFO = "PARAM_INFO"
DRIVER_INFO = "DRIVER_INFO"
IN_MODE_SUFFIX = ":IN_MODE"
SP_SUFFIX = ":SP"
SP_RBV_SUFFIX = ":SP:RBV"
ACTION_SUFFIX = ":ACTION"
SET_AND_NO_ACTION_SUFFIX = ":SP_NO_ACTION"
RBV_AT_SP = ":RBV:AT_SP"
CHANGING = ":CHANGING"
CHANGED_SUFFIX = ":CHANGED"
DEFINE_POSITION_AS = ":DEFINE_POSITION_AS"

VAL_FIELD = ".VAL"

FOOTPRINT_PREFIX = "FP"

SAMPLE_LENGTH = "{}:{}".format(FOOTPRINT_PREFIX, "SAMPLE_LENGTH")
FP_TEMPLATE = "{}:{{}}:{}".format(FOOTPRINT_PREFIX, "FOOTPRINT")
DQQ_TEMPLATE = "{}:{{}}:{}".format(FOOTPRINT_PREFIX, "DQQ")
QMIN_TEMPLATE = "{}:{{}}:{}".format(FOOTPRINT_PREFIX, "QMIN")
QMAX_TEMPLATE = "{}:{{}}:{}".format(FOOTPRINT_PREFIX, "QMAX")

FP_SP_PREFIX = "SP"
FP_SP_RBV_PREFIX = "SP_RBV"
FP_RBV_PREFIX = "RBV"

FOOTPRINT_PREFIXES = [FP_SP_PREFIX, FP_SP_RBV_PREFIX, FP_RBV_PREFIX]

PARAM_FIELDS_BINARY = {'type': 'enum', 'enums': ["NO", "YES"]}

PARAM_IN_MODE = {'type': 'enum', 'enums': ["NO", "YES"]}

PARAM_FIELDS_ACTION = {'type': 'int', 'count': 1, 'value': 0}

OUT_IN_ENUM_TEXT = ["OUT", "IN"]

STANDARD_FLOAT_PV_FIELDS = {'type': 'float', 'prec': 3, 'value': 0.0}

PARAMS_FIELDS_BEAMLINE_TYPES = {
    BeamlineParameterType.IN_OUT: {'type': 'enum', 'enums': OUT_IN_ENUM_TEXT},
    BeamlineParameterType.FLOAT: STANDARD_FLOAT_PV_FIELDS}


def convert_to_epics_pv_value(parameter_type, value):
    """
    Convert from parameter value to the epic pv value
    Args:
        parameter_type (BeamlineParameterType): parameters type
        value: value to convert

    Returns: epics value

    """
    if parameter_type == BeamlineParameterType.IN_OUT:
        if value:
            return OUT_IN_ENUM_TEXT.index("IN")
        else:
            return OUT_IN_ENUM_TEXT.index("OUT")
    else:
        if value is None:
            return float("NaN")
        else:
            return value


def convert_from_epics_pv_value(parameter_type, value):
    """
    Convert from epic pv value to the parameter value
    Args:
        parameter_type (BeamlineParameterType): parameters type
        value: value to convert

    Returns: epics value

    """
    if parameter_type == BeamlineParameterType.IN_OUT:
        return value == OUT_IN_ENUM_TEXT.index("IN")
    else:
        return value


class PvSort(Enum):
    """
    Enum for the type of PV
    """
    RBV = 0
    ACTION = 1
    SP_RBV = 2
    SP = 3
    SET_AND_NO_ACTION = 4
    CHANGED = 6
    IN_MODE = 7
    CHANGING = 8
    RBV_AT_SP = 9
    DEFINE_POS_AS = 10

    @staticmethod
    def what(pv_sort):
        """
        Args:
            pv_sort: pv sort to determine

        Returns: what the pv sort does
        """
        if pv_sort == PvSort.RBV:
            return ""
        elif pv_sort == PvSort.ACTION:
            return "(Do the action)"
        elif pv_sort == PvSort.SP_RBV:
            return "(Set point readback)"
        elif pv_sort == PvSort.SP:
            return "(Set point)"
        elif pv_sort == PvSort.SET_AND_NO_ACTION:
            return "(Set point with no action executed)"
        elif pv_sort == PvSort.CHANGED:
            return "(Is changed)"
        elif pv_sort == PvSort.IN_MODE:
            return "(Is in mode)"
        elif pv_sort == PvSort.CHANGING:
            return "(Is changing)"
        elif pv_sort == PvSort.RBV_AT_SP:
            return "(Tolerance between RBV and target set point)"
        elif pv_sort == PvSort.DEFINE_POS_AS:
            return "(Define the value of current position)"
        else:
            print_and_log("Unknown pv sort!! {}".format(pv_sort), severity=SEVERITY.MAJOR, src="REFL")
            return "(unknown)"

    def get_from_parameter(self, parameter):
        """
        Get the value of the correct sort from a parameter
        Args:
            parameter(ReflectometryServer.parameters.BeamlineParameter): the parameter to get the value from

        Returns: the value of the parameter of the correct sort
        """
        if self == PvSort.SP:
            return convert_to_epics_pv_value(parameter.parameter_type, parameter.sp)
        elif self == PvSort.SP_RBV:
            return convert_to_epics_pv_value(parameter.parameter_type, parameter.sp_rbv)
        elif self == PvSort.RBV:
            return convert_to_epics_pv_value(parameter.parameter_type, parameter.rbv)
        elif self == PvSort.SET_AND_NO_ACTION:
            return convert_to_epics_pv_value(parameter.parameter_type, parameter.sp_no_move)
        elif self == PvSort.CHANGED:
            return parameter.sp_changed
        elif self == PvSort.ACTION:
            return parameter.move
        elif self == PvSort.CHANGING:
            return parameter.is_changing
        elif self == PvSort.RBV_AT_SP:
            return parameter.rbv_at_sp
        return float("NaN")


class FootprintSort(Enum):
    """
    Enum for the type of footprint calculator
    """
    SP = 0
    RBV = 1
    SP_RBV = 2

    @staticmethod
    def prefix(sort):
        """
        Args:
            sort: The sort of footprint value

        Returns: The pv suffix for this sort of value
        """
        if sort == FootprintSort.SP:
            return FP_SP_PREFIX
        elif sort == FootprintSort.SP_RBV:
            return FP_SP_RBV_PREFIX
        elif sort == FootprintSort.RBV:
            return FP_RBV_PREFIX
        return None


class PVManager:
    """
    Holds reflectometry PVs and associated utilities.
    """
    def __init__(self, beamline):
        """
        The constructor.
        Args:
            beamline (ReflectometryServer.beamline.Beamline): the beamline to create the manager for
        """
        self._beamline = beamline
        self.PVDB = {}
        self._params_pv_lookup = OrderedDict()
        self._footprint_parameters = {}

        self._add_global_pvs()
        self._add_footprint_calculator_pvs()
        self._add_all_parameter_pvs()
        self._add_all_driver_pvs()

        for pv_name in self.PVDB.keys():
            print("creating pv: {}".format(pv_name))

    def _add_global_pvs(self):
        """
        Add PVs that affect the whole of the reflectometry system to the server's PV database.

        """
        self._add_pv_with_val(BEAMLINE_MOVE, None, PARAM_FIELDS_ACTION, "Move the beam line", PvSort.RBV, archive=True,
                              interest="HIGH")
        # PVs for mode
        mode_fields = {'type': 'enum', 'enums': self._beamline.mode_names}
        self._add_pv_with_val(BEAMLINE_MODE, None, mode_fields, "Beamline mode", PvSort.RBV, archive=True,
                              interest="HIGH")
        self._add_pv_with_val(BEAMLINE_MODE + SP_SUFFIX, None, mode_fields, "Beamline mode", PvSort.SP)

        # PVs for server status
        status_fields = {'type': 'enum',
                         'enums': [code.display_string for code in self._beamline.status_codes],
                         'states': [code.alarm_severity for code in self._beamline.status_codes]}
        self._add_pv_with_val(BEAMLINE_STATUS, None, status_fields, "Status of the beam line", PvSort.RBV, archive=True,
                              interest="HIGH", alarm=True)
        self._add_pv_with_val(BEAMLINE_MESSAGE, None, {'type': 'char', 'count': 400}, "Message about the beamline",
                              PvSort.RBV, archive=True, interest="HIGH")

    def _add_footprint_calculator_pvs(self):
        """
        Add PVs related to the footprint calculation to the server's PV database.
        """
        self._add_pv_with_val(SAMPLE_LENGTH, None, STANDARD_FLOAT_PV_FIELDS,
                              "Sample Length", PvSort.SP_RBV, archive=True, interest="HIGH")

        for prefix in FOOTPRINT_PREFIXES:
            for template, description in [(FP_TEMPLATE, "Beam Footprint"),
                                          (DQQ_TEMPLATE, "Beam Resolution dQ/Q"),
                                          (QMIN_TEMPLATE, "Minimum measurable Q with current setup"),
                                          (QMAX_TEMPLATE, "Maximum measurable Q with current setup")]:
                self._add_pv_with_val(template.format(prefix), None,
                                      STANDARD_FLOAT_PV_FIELDS,
                                      description, PvSort.RBV, archive=True, interest="HIGH")

    def _add_all_parameter_pvs(self):
        """
        Add PVs for each beamline parameter in the reflectometry configuration to the server's PV database.
        """
        param_info = []
        for param, (param_type, group_names, description) in self._beamline.parameter_types.items():
            param_info_record = self._add_parameter_pvs(param, group_names, description, param_type)
            param_info.append(param_info_record)
        self.PVDB[PARAM_INFO] = {'type': 'char',
                                 'count': 2048,
                                 'value': compress_and_hex(json.dumps(param_info))
                                 }
    
    def _add_parameter_pvs(self, param_name, group_names, description, param_type):
        """
        Adds all PVs needed for one beamline parameter to the PV database.

        Args:
            param_name: The name of the beamline parameter
            param_type: The type of the parameter
            group_names: list of groups to which this parameter belong
            description: description of the pv

        Returns:
            parameter information
        """
        try:
            param_alias = create_pv_name(param_name, self.PVDB.keys(), PARAM_PREFIX, limit=10)
            prepended_alias = "{}:{}".format(PARAM_PREFIX, param_alias)
           
            fields = PARAMS_FIELDS_BEAMLINE_TYPES[param_type]

            self.PVDB["{}.DESC".format(prepended_alias)] = {'type': 'string',
                                                            'value': description
                                                            }

            # Readback PV
            self._add_pv_with_val(prepended_alias, param_name, fields, description, PvSort.RBV, archive=True,
                                  interest="HIGH")

            # Setpoint PV
            self._add_pv_with_val(prepended_alias + SP_SUFFIX, param_name, fields, description, PvSort.SP, archive=True)

            # Setpoint readback PV
            self._add_pv_with_val(prepended_alias + SP_RBV_SUFFIX, param_name, fields, description, PvSort.SP_RBV)

            # Set value and do not action PV
            self._add_pv_with_val(prepended_alias + SET_AND_NO_ACTION_SUFFIX, param_name, fields, description,
                                  PvSort.SET_AND_NO_ACTION)

            # Changed PV
            self._add_pv_with_val(prepended_alias + CHANGED_SUFFIX, param_name, PARAM_FIELDS_BINARY, description,
                                  PvSort.CHANGED)

            # Action PV
            self._add_pv_with_val(prepended_alias + ACTION_SUFFIX, param_name, PARAM_FIELDS_ACTION, description,
                                  PvSort.ACTION)

            # Moving state PV
            self._add_pv_with_val(prepended_alias + CHANGING, param_name, PARAM_FIELDS_BINARY, description,
                                  PvSort.CHANGING)

            # In mode PV
            self._add_pv_with_val(prepended_alias + IN_MODE_SUFFIX, param_name, PARAM_IN_MODE, description,
                                  PvSort.IN_MODE)

            # RBV to SP:RBV tolerance
            self._add_pv_with_val(prepended_alias + RBV_AT_SP, param_name, PARAM_FIELDS_BINARY, description,
                                  PvSort.RBV_AT_SP)

            # define position at
            self._add_pv_with_val(prepended_alias + DEFINE_POSITION_AS, param_name, STANDARD_FLOAT_PV_FIELDS,
                                  description, PvSort.DEFINE_POS_AS)

            return {"name": param_name,
                    "prepended_alias": prepended_alias,
                    "type": BeamlineParameterType.name_for_param_list(param_type)}

        except Exception as err:
            print("Error adding parameter PV: " + err.message)

    def _add_pv_with_val(self, pv_name, param_name, pv_fields, description, sort, archive=False, interest=None,
                         alarm=False):
        """
        Add param to pv list with .val and correct fields and to parm look up
        Args:
            pv_name: name of the pv
            param_name: name of the parameter; None for not a parameter
            pv_fields: pv fields to use
            sort: sort of pv it is
            archive: True if it should be archived
            interest: level of interest; None is not interesting
            alarm: True if this pv represents the alarm state of the IOC; false otherwise

        Returns:

        """
        pv_fields = pv_fields.copy()
        pv_fields[PV_DESCRIPTION_NAME] = description + PvSort.what(sort)

        pv_fields_mod = pv_fields.copy()
        pv_fields_mod[PV_INFO_FIELD_NAME] = {}
        if interest is not None:
            pv_fields_mod[PV_INFO_FIELD_NAME]["INTEREST"] = interest
        if archive:
            pv_fields_mod[PV_INFO_FIELD_NAME]["archive"] = "VAL"
        if alarm:
            pv_fields_mod[PV_INFO_FIELD_NAME]["alarm"] = "Reflectometry IOC (REFL)"

        self.PVDB[pv_name] = pv_fields_mod
        self.PVDB[pv_name + VAL_FIELD] = pv_fields

        if param_name is not None:
            self._params_pv_lookup[pv_name] = (param_name, sort)

    def _add_all_driver_pvs(self):
        """
        Add all pvs for the drivers.
        """
        self.drivers_pv = {}
        driver_info = []
        for driver in self._beamline.drivers:
            if driver.has_engineering_correction:
                correction_alias = create_pv_name(driver.name, self.PVDB.keys(), "COR", limit=12, allow_colon=True)
                prepended_alias = "{}:{}".format("COR", correction_alias)

                self.PVDB[prepended_alias] = STANDARD_FLOAT_PV_FIELDS
                self.PVDB[prepended_alias + VAL_FIELD] = STANDARD_FLOAT_PV_FIELDS
                self.PVDB["{}.DESC".format(prepended_alias)] = {'type': 'char', 'count': 100, 'value': ""}

                self.drivers_pv[driver] = prepended_alias

                driver_info.append({"name": driver.name, "prepended_alias": prepended_alias})
        self.PVDB[DRIVER_INFO] = {'type': 'char',
                                  'count': 2048,
                                  'value': compress_and_hex(json.dumps(driver_info))}

    def param_names_pv_names_and_sort(self):
        """

        Returns:
            (list[str, tuple[str, PvSort]]): The list of PVs of all beamline parameters.

        """
        return self._params_pv_lookup.items()

    def is_param(self, pv_name):
        """

        Args:
            pv_name: name of the pv

        Returns:
            True if the pv is a pv for beamline parameter
        """
        return remove_from_end(pv_name, VAL_FIELD) in self._params_pv_lookup

    def get_param_name_and_sort_from_pv(self, pv_name):
        """
        Args:
            pv_name: name of pv to find

        Returns:
            (str, PvSort): parameter name and sort for the given pv
        """
        return self._params_pv_lookup[remove_from_end(pv_name, VAL_FIELD)]

    def is_beamline_mode(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the beamline mode pv
        """
        pv_name_no_val = remove_from_end(pv_name, VAL_FIELD)
        return pv_name_no_val == BEAMLINE_MODE or pv_name_no_val == BEAMLINE_MODE + SP_SUFFIX

    def is_beamline_move(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the beamline move pv
        """
        return self._is_pv_name_this_field(BEAMLINE_MOVE, pv_name)

    def is_tracking_axis(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the beamline tracking axis pv
        """
        return self._is_pv_name_this_field(PARAM_INFO, pv_name)

    def is_beamline_status(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the beamline status pv
        """
        return self._is_pv_name_this_field(BEAMLINE_STATUS, pv_name)

    def is_beamline_message(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the beamline message pv
        """
        return self._is_pv_name_this_field(BEAMLINE_MESSAGE, pv_name)

    def is_sample_length(self, pv_name):
        """
        Args:
            pv_name: name of the pv

        Returns: True if this the sample length pv
        """
        return self._is_pv_name_this_field(SAMPLE_LENGTH, pv_name)

    def _is_pv_name_this_field(self, field_name, pv_name):
        """
        Args:
            field_name: field name to match
            pv_name: pv name to match

        Returns: True if field name is pv name (with oe without VAL  field)

        """
        pv_name_no_val = remove_from_end(pv_name, VAL_FIELD)
        return pv_name_no_val == field_name
