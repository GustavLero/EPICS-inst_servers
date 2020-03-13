"""
Parameters that the user would interact with
"""
from collections import namedtuple

from ReflectometryServer.beam_path_calc import BeamPathUpdate, ComponentChangingUpdate, InitUpdate
from ReflectometryServer.file_io import param_float_autosave, param_bool_autosave
import logging

from enum import Enum
from ReflectometryServer.components import ChangeAxis
import abc
import six

from ReflectometryServer.pv_wrapper import ReadbackUpdate, IsChangingUpdate
from server_common.observable import observable

logger = logging.getLogger(__name__)

# An update of the parameter readback value
ParameterReadbackUpdate = namedtuple("ParameterReadbackUpdate", [
    "value",            # The new readback value of the parameter
    "alarm_severity",   # The alarm severity of the parameter, represented as an integer (see Channel Access doc)
    "alarm_status"])    # The alarm status of the parameter, represented as an integer (see Channel Access doc)

# An update of the parameter setpoint readback value
ParameterSetpointReadbackUpdate = namedtuple("ParameterSetpointReadbackUpdate", [
    "value"])           # The new setpoint readback value of the parameter

# An update of the parameter at-setpoint state
ParameterAtSetpointUpdate = namedtuple("ParameterAtSetpointUpdate", [
    "value"])           # The new state (boolean)

# An update of the parameter is-changing state
ParameterChangingUpdate = namedtuple("ParameterChangingUpdate", [
    "value"])           # The new state (boolean)

# An update that is triggered when the parameter has received an initial value either from autosave or motor rbv.
ParameterInitUpdate = namedtuple("ParameterInitUpdate", [
    "value"])           # The initial parameter value


class ParameterNotInitializedException(Exception):
    """
    Exception for when a parameter is not initialized.
    """
    def __init__(self, err):
        self.message = str(err)

    def __str__(self):
        return self.message


class DefineCurrentValueAsParameter(object):
    """
    A helper class which allows the current parameter readback to be set to a particular value by passing it down to the
    lower levels.
    """
    def __init__(self, define_current_value_as_fn, set_point_change_fn, parameter):
        self._new_value = 0.0
        self._define_current_value_as_fn = define_current_value_as_fn
        self._set_point_change_fn = set_point_change_fn
        self._parameter = parameter

    @property
    def new_value(self):
        """
        Returns: The last value set
        """
        return self._new_value

    @new_value.setter
    def new_value(self, value):
        """
        Set the new value and pass it down to the next layer
        Args:
            value: the new value to set the parameter to
        """
        logger.info("Defining position for parameter {name} to {new_value}. "
                    "From sp {sp}, sp_rbv {sp_rbv} and rbv {rbv}"
                    .format(name=self._parameter.name,
                            new_value=value,
                            sp=self._parameter.sp,
                            sp_rbv=self._parameter.sp_rbv,
                            rbv=self._parameter.rbv))

        self._new_value = value
        self._define_current_value_as_fn(value)
        self._set_point_change_fn(value)


class BeamlineParameterType(Enum):
    """
    Types of beamline parameters
    """
    FLOAT = 0
    IN_OUT = 1

    @staticmethod
    def name_for_param_list(param_type):
        """
        Returns: Type of parameter for the parameters list
        """
        if param_type is BeamlineParameterType.FLOAT:
            return "float"
        elif param_type is BeamlineParameterType.IN_OUT:
            return "in_out"
        else:
            raise ValueError("Parameter doesn't have recognised type {}".format(param_type))


class BeamlineParameterGroup(Enum):
    """
    Types of groups a parameter can belong to
    """
    TRACKING = 1
    FOOTPRINT_PARAMETER = 2
    GAP_VERTICAL = 3
    GAP_HORIZONTAL = 4


@observable(ParameterReadbackUpdate, ParameterSetpointReadbackUpdate, ParameterAtSetpointUpdate, ParameterChangingUpdate, ParameterInitUpdate)
@six.add_metaclass(abc.ABCMeta)
class BeamlineParameter(object):
    """
    General beamline parameter that can be set. Subclass must implement _move_component to decide what to do with the
    value that is set.
    """

    def __init__(self, name, sim=False, init=None, description=None, autosave=False, rbv_to_sp_tolerance=0.01):
        if sim:
            self._set_point = init
            self._set_point_rbv = init
        else:
            self._set_point = None
            self._set_point_rbv = None

        self._sp_is_changed = False
        self._name = name
        self.alarm_status = None
        self.alarm_severity = None
        self.after_move_listener = lambda x: None
        self.parameter_type = BeamlineParameterType.FLOAT
        if description is None:
            self.description = name
        else:
            self.description = description
        self._autosave = autosave
        self.group_names = []
        self._rbv_to_sp_tolerance = rbv_to_sp_tolerance

        self.define_current_value_as = None

    def __repr__(self):
        return "{} '{}': sp={}, sp_rbv={}, rbv={}, changed={}".format(__name__, self.name, self._set_point,
                                                                      self._set_point_rbv, self.rbv, self.sp_changed)

    @abc.abstractmethod
    def _initialise_sp_from_file(self):
        """
        Read an autosaved setpoint for this parameter from the autosave file. Remains None if unsuccessful.
        Subclassed to handle type casting.
        """

    @abc.abstractmethod
    def _initialise_sp_from_motor(self, _):
        """
        Get the setpoint value for this parameter based on the motor setpoint position.
        """

    def _set_initial_sp(self, sp_init):
        """
        Populate the setpoint and setpoint readback with a value and trigger relevant listeners.

        Args:
            sp_init: The setpoint value to set
        """
        self._set_point = sp_init
        self._set_point_rbv = sp_init
        self.trigger_listeners(ParameterInitUpdate(self._set_point))

    @abc.abstractmethod
    def _set_changed_flag(self):
        """
        Flags in the component that the beamline parameter should be moved.
        """

    @property
    def rbv(self):
        """
        Returns: the read back value
        """
        return self._rbv()

    @property
    def rbv_at_sp(self):
        """
        Returns: Does the read back value match the set point target within a defined tolerance
        """
        if self.rbv is None or self._set_point_rbv is None:
            return False

        return abs(self.rbv - self._set_point_rbv) < self._rbv_to_sp_tolerance

    @property
    def sp_rbv(self):
        """
        Returns: the set point read back value, i.e. where the last move was instructed to go
        """
        return self._set_point_rbv

    @property
    def sp_no_move(self):
        """
        The set point of where it will move to when move is set.

        Returns: Setpoint last set, i.e. when the next move on this parameter is called where it will move to
        """
        return self._set_point

    @sp_no_move.setter
    def sp_no_move(self, set_point):
        """
        The set point of where it will move to when move is set.
        Move is not done this is mainly for use in the OPI.
        Args:
            set_point: the set point
        """
        self._sp_no_move(set_point)

    def _sp_no_move(self, set_point):
        self._set_point = set_point
        self._sp_is_changed = True

    @property
    def sp(self):
        """
        Move to this setpoint.
        Returns: Setpoint last set, i.e. when the next move on this parameter is called where it will move to
        """
        return self._set_point

    @sp.setter
    def sp(self, value):
        """
        Set the set point and move to it.
        Args:
            value: new set point
        """
        self._set_sp(value)

    def _set_sp(self, value):
        """
        Set the set point and move to do, private function needed for define position
        Args:
            value: new set point
        """
        self._sp_no_move(value)
        self._do_move()

    @property
    def move(self):
        """
        Move to the setpoint.
        """
        return 0

    @move.setter
    def move(self, _):
        """
        Move to the setpoint, no matter what the value passed is.
        """
        self._do_move()

    def _do_move(self):
        self.move_to_sp_no_callback()
        self.after_move_listener(self)

    def move_to_sp_no_callback(self):
        """
        Move the component but don't call a callback indicating a move has been performed.
        """
        self._set_point_rbv = self._set_point
        self._check_and_move_component()
        self._sp_is_changed = False
        if self._autosave:
            param_float_autosave.write_parameter(self._name, self._set_point_rbv)
        self._on_update_sp_rbv()

    def move_to_sp_rbv_no_callback(self):
        """
        Repeat the move to the last set point.
        """
        self._check_and_move_component()

    def _on_update_rbv(self, source):
        """
        Trigger all rbv listeners

        Args:
            source: source of change which is not used
        """
        rbv = self._rbv()
        self._update_alarms()
        self.trigger_listeners(ParameterReadbackUpdate(rbv, self.alarm_severity, self.alarm_status))
        self.trigger_listeners(ParameterAtSetpointUpdate(self.rbv_at_sp))

    def _update_alarms(self):
        """
        To be implemented in subclass
        """
        alarm_info = self._get_alarm_info()
        if alarm_info is not None:
            self.alarm_severity = alarm_info[0]
            self.alarm_status = alarm_info[1]

    def _get_alarm_info(self):
        """
        To be implemented in subclass
        """
        raise NotImplemented()

    @property
    def is_changing(self):
        """
        Returns: Is the parameter changing (rotating, displacing etc.)
        """
        raise NotImplemented()

    def _on_update_changing_state(self, update):
        """
        Runs all the current listeners on the changing state because something has changed.

        Args:
            update (ReflectometryServer.beam_path_calc.ComponentChangingUpdate): The update event
        """
        self.trigger_listeners(ParameterChangingUpdate(self.is_changing))

    def _on_update_sp_rbv(self):
        """
        Trigger all rbv listeners
        """
        self.trigger_listeners(ParameterSetpointReadbackUpdate(self._set_point_rbv))
        self.trigger_listeners(ParameterAtSetpointUpdate(self.rbv_at_sp))

    @property
    def name(self):
        """
        Returns:
            (str): name of this beamline parameter
        """
        return self._name

    @property
    def sp_changed(self):
        """
        Returns: Has set point been changed since the last move
        """
        return self._sp_is_changed

    def _check_and_move_component(self):
        """
        Checks whether this parameter is initialised and moves the underlying component to its setpoint if so.
        """
        if self._set_point_rbv is not None:
            self._move_component()
            self._set_changed_flag()
        else:
            raise ParameterNotInitializedException(self.name)

    @abc.abstractmethod
    def _move_component(self):
        """
        Moves the component(s) associated with this parameter to the setpoint.
        """

    @abc.abstractmethod
    def _rbv(self):
        """
        Returns: the read back value
        """

    @abc.abstractmethod
    def validate(self, drivers):
        """
        Perform validation of this parameter returning a list of errors.

        Args:
            drivers (list[ReflectometryServer.ioc_driver.IocDriver]): list of driver to help with validation

        Returns:
            (list[str]): list of problems; Empty list if there are no errors

        """

    def _log_autosave_type_error(self):
        """
        Logs an error that the autosave value this parameter was trying to read was of the wrong type.
        """
        logger.error("Could not read autosave value for parameter {}: unexpected type.".format(self.name))


class AngleParameter(BeamlineParameter):
    """
    The angle of the component measured from the incoming beam, this could be theta, or the supermirror angle or
        title jaws angle.
    Angle is measure with +ve in the anti-clockwise direction)
    """

    def __init__(self, name, angled_component, sim=False, init=0, description=None, autosave=False,
                 rbv_to_sp_tolerance=0.002):
        """
        Initializer.
        Args:
            name (str): Name of the reflection angle
            angled_component (ReflectometryServer.components.Component): the active component that can contain an angle
                either because it is reflecting or tilting.
            description (str): description
        """
        if description is None:
            description = "{} angle".format(name)
        super(AngleParameter, self).__init__(name, sim, init, description, autosave,
                                             rbv_to_sp_tolerance=rbv_to_sp_tolerance)
        self._reflection_component = angled_component

        if self._autosave:
            self._initialise_sp_from_file()
        if self._set_point_rbv is None:
            self._reflection_component.beam_path_set_point.add_listener(InitUpdate, self._initialise_sp_from_motor)

        self._reflection_component.beam_path_rbv.add_listener(BeamPathUpdate, self._on_update_rbv)
        self._reflection_component.beam_path_rbv.add_listener(ComponentChangingUpdate,
                                                              self._on_update_changing_state)

        if self._reflection_component.can_define_current_angle_as:
            self.define_current_value_as = DefineCurrentValueAsParameter(
                self._reflection_component.define_current_angle_as, self._set_sp, self)

    def _initialise_sp_from_file(self):
        """
        Read an autosaved setpoint for this parameter from the autosave file. Remains None if unsuccessful.
        """
        sp_init = param_float_autosave.read_parameter(self._name, None)
        if sp_init is not None:
            self._set_initial_sp(sp_init)
            self._reflection_component.beam_path_set_point.autosaved_angle = sp_init
            self._move_component()

    def _initialise_sp_from_motor(self, _):
        """
        Get the setpoint value for this parameter based on the motor setpoint position.
        """
        init_sp = self._reflection_component.beam_path_set_point.get_angle_relative_to_beam()
        self._set_initial_sp(init_sp)

    def _move_component(self):
        self._reflection_component.beam_path_set_point.set_angle_relative_to_beam(self._set_point_rbv)

    def _set_changed_flag(self):
        self._reflection_component.set_changed_flag(ChangeAxis.ANGLE, True)

    def _rbv(self):
        return self._reflection_component.beam_path_rbv.get_angle_relative_to_beam()

    def _get_alarm_info(self):
        """
        Returns the alarm information for the angle axis of this component.
        """
        return self._reflection_component.beam_path_rbv.angle_alarm

    @property
    def is_changing(self):
        """
        Returns: Is the parameter changing (rotating)
        """
        return self._reflection_component.beam_path_rbv.is_rotating

    def validate(self, drivers):
        """
        Perform validation of this parameter returning a list of errors.

        Args:
            drivers (list[ReflectometryServer.ioc_driver.IocDriver]): list of driver to help with validation

        Returns:
            (list[str]): list of problems; Empty list if there are no errors

        """
        return []


class TrackingPosition(BeamlineParameter):
    """
    Component which tracks the position of the beam with a single degree of freedom. E.g. slit set on a height stage
    """

    def __init__(self, name, component, sim=False, init=0, description=None, autosave=False, rbv_to_sp_tolerance=0.002):
        """

        Args:
            name: Name of the variable
            component (ReflectometryServer.components.Component): component that the tracking is based on
            description (str): description
        """
        if description is None:
            description = "{} tracking position".format(name)
        super(TrackingPosition, self).__init__(name, sim, init, description, autosave,
                                               rbv_to_sp_tolerance=rbv_to_sp_tolerance)
        self._component = component

        if self._autosave:
            self._initialise_sp_from_file()
        if self._set_point_rbv is None:
            self._component.beam_path_set_point.add_listener(InitUpdate, self._initialise_sp_from_motor)

        self._component.beam_path_rbv.add_listener(BeamPathUpdate, self._on_update_rbv)
        self._component.beam_path_rbv.add_listener(ComponentChangingUpdate, self._on_update_changing_state)

        self.group_names.append(BeamlineParameterGroup.TRACKING)

        self.define_current_value_as = DefineCurrentValueAsParameter(
            self._component.define_current_position_as, self._set_sp, self)

    def _initialise_sp_from_file(self):
        """
        Read an autosaved setpoint for this parameter from the autosave file. Remains None if unsuccessful.
        """
        sp_init = param_float_autosave.read_parameter(self._name, None)
        if sp_init is not None:
            self._set_initial_sp(sp_init)
            self._component.beam_path_set_point.autosaved_offset = sp_init
            self._move_component()

    def _initialise_sp_from_motor(self, _):
        """
        Get the setpoint value for this parameter based on the motor setpoint position.
        """
        if self._component.beam_path_set_point.is_in_beam:
            init_sp = self._component.beam_path_set_point.get_position_relative_to_beam()
        else:
            init_sp = 0.0
        self._set_initial_sp(init_sp)

    def _move_component(self):
        self._component.beam_path_set_point.set_position_relative_to_beam(self._set_point_rbv)

    def _set_changed_flag(self):
        self._component.set_changed_flag(ChangeAxis.POSITION, True)

    def _rbv(self):
        """
        Returns: readback value for the tracking displacement above the beam
        """
        return self._component.beam_path_rbv.get_position_relative_to_beam()

    def _get_alarm_info(self):
        """
        Returns the alarm information for the displacement axis of this component.
        """
        return self._component.beam_path_rbv.displacement_alarm

    @property
    def rbv_at_sp(self):
        """
        Returns: Does the read back value match the set point target within a defined tolerance and the component is in
            the beam
        """
        if self.rbv is None or self._set_point_rbv is None:
            return False

        return not self._component.beam_path_set_point.is_in_beam or \
            abs(self.rbv - self._set_point_rbv) <= self._rbv_to_sp_tolerance

    @property
    def is_changing(self):
        """
        Returns: Is the parameter changing (displacing)
        """
        return self._component.beam_path_rbv.is_displacing

    def validate(self, drivers):
        """
        Perform validation of this parameter returning a list of errors.

        Args:
            drivers (list[ReflectometryServer.ioc_driver.IocDriver]): list of driver to help with validation

        Returns:
            (list[str]): list of problems; Empty list if there are no errors

        """
        return []


class InBeamParameter(BeamlineParameter):
    """
    Parameter which sets whether a given device is in the beam.
    """

    def __init__(self, name, component, sim=False, init=False, description=None, autosave=False):
        """
        Initializer.
        Args:
            name (str): Name of the enabled parameter
            component (ReflectometryServer.components.Component): the component to be enabled or disabled
            description (str): description
        """
        if description is None:
            description = "{} component is in the beam".format(name)
        super(InBeamParameter, self).__init__(name, sim, init, description, autosave, rbv_to_sp_tolerance=0.001)
        self._component = component

        if self._autosave:
            self._initialise_sp_from_file()
        if self._set_point_rbv is None:
            self._component.beam_path_set_point.add_listener(InitUpdate, self._initialise_sp_from_motor)
        self._component.beam_path_rbv.add_listener(BeamPathUpdate, self._on_update_rbv)
        self._component.beam_path_rbv.add_listener(ComponentChangingUpdate, self._on_update_changing_state)

        self.parameter_type = BeamlineParameterType.IN_OUT

    def _initialise_sp_from_file(self):
        """
        Read an autosaved setpoint for this parameter from the autosave file. Remains None if unsuccessful.
        """
        sp_init = param_bool_autosave.read_parameter(self._name, None)
        if sp_init is not None:
            self._set_initial_sp(sp_init)
            self._move_component()

    def _initialise_sp_from_motor(self, _):
        """
        Get the setpoint value for this parameter based on the motor setpoint position.
        """
        init_sp = self._component.beam_path_set_point.is_in_beam
        self._set_initial_sp(init_sp)

    def _move_component(self):
        self._component.beam_path_set_point.is_in_beam = self._set_point_rbv

    def _set_changed_flag(self):
        self._component.set_changed_flag(ChangeAxis.POSITION, True)

    def validate(self, drivers):
        """
        Perform validation of this parameter returning a list of errors.

        Args:
            drivers (list[ReflectometryServer.ioc_driver.IocDriver]): list of driver to help with validation

        Returns:
            (list[str]): list of problems; Empty list if there are no errors
        """

        errors = []
        for driver in drivers:
            if driver.is_for_component(self._component):
                try:
                    if driver.has_out_of_beam_position():
                        break
                except AttributeError:
                    pass  # this is not a displacement driver so can not have this
        else:
            errors.append("No driver found with out of beam position for component {}".format(self.name))
        return errors

    def _rbv(self):
        return self._component.beam_path_rbv.is_in_beam

    def _get_alarm_info(self):
        """
        Returns the alarm information for the displacement axis of this component.
        """
        return self._component.beam_path_rbv.displacement_alarm

    @property
    def rbv_at_sp(self):
        """
        Returns: Does the read back value match the set point target within a defined tolerance
        """
        if self.rbv is None or self._set_point_rbv is None:
            return False

        return abs(self.rbv - self._set_point_rbv) < self._rbv_to_sp_tolerance

    @property
    def is_changing(self):
        """
        Returns: Is the parameter changing (rotating, displacing etc.)
        """
        return self._component.beam_path_rbv.is_displacing


class SlitGapParameter(BeamlineParameter):
    """
    Parameter which sets the gap on a slit. This differs from other beamline parameters in that it is not linked to the
    beamline component layer but hooks directly into a motor axis.
    """

    def __init__(self, name, pv_wrapper, sim=False, init=0, description=None, autosave=False,
                 rbv_to_sp_tolerance=0.002):
        """
        Args:
            name (str): The name of the parameter
            pv_wrapper (ReflectometryServer.pv_wrapper._JawsAxisPVWrapper): The jaws pv wrapper this parameter talks to
            sim (bool): Whether it is a simulated parameter
            init (float): Initialisation value if simulated
            description (str): The description
        """
        super(SlitGapParameter, self).__init__(name, sim, init, description, autosave,
                                               rbv_to_sp_tolerance=rbv_to_sp_tolerance)
        self._last_update = None

        self._pv_wrapper = pv_wrapper
        self._pv_wrapper.add_listener(ReadbackUpdate, self._on_update_slit_rbv)
        self._pv_wrapper.add_listener(IsChangingUpdate, self._on_is_changing_change)
        self._pv_wrapper.initialise()
        if pv_wrapper.is_vertical:
            self.group_names.append(BeamlineParameterGroup.FOOTPRINT_PARAMETER)
            self.group_names.append(BeamlineParameterGroup.GAP_VERTICAL)
        else:
            self.group_names.append(BeamlineParameterGroup.GAP_HORIZONTAL)

        if self._autosave:
            self._initialise_sp_from_file()
        if self._set_point_rbv is None:
            self._initialise_sp_from_motor(None)
        if sim:
            self._last_update = ReadbackUpdate(init, None, None)

        self._no_move_because_is_define = False
        self.define_current_value_as = DefineCurrentValueAsParameter(self._pv_wrapper.define_position_as,
                                                                     self._set_sp_perform_no_move, self)

    def _initialise_sp_from_file(self):
        """
        Read an autosaved setpoint for this parameter from the autosave file. Remains None if unsuccessful.
        """
        sp_init = param_float_autosave.read_parameter(self._name, None)
        if sp_init is not None:
            self._set_initial_sp(sp_init)

    def _initialise_sp_from_motor(self, _):
        """
        Get the setpoint value for this parameter based on the motor setpoint position.
        """
        self._set_initial_sp(self._pv_wrapper.sp)

    def _on_update_slit_rbv(self, update):
        """
        Update the readback value.

        Args:
            update (ReflectometryServer.pv_wrapper.ReadbackUpdate): update of the readback value of the axis
        """
        self._last_update = update
        self._on_update_rbv(self)

    def _set_changed_flag(self):
        pass

    def _move_component(self):
        if not self._no_move_because_is_define:
            self._pv_wrapper.sp = self._set_point_rbv

    def _set_sp_perform_no_move(self, new_value):
        """
        This is a work around because this does not have a component. See ticket 4902
        When stripping out get rid of _no_move_because_is_define
        Args:
            new_value: the new value for the setpoint
        """
        try:
            self._no_move_because_is_define = True
            self._set_sp(new_value)
        finally:
            self._no_move_because_is_define = False

    def _rbv(self):
        return self._last_update.value

    def _get_alarm_info(self):
        """
        Returns the alarm information for this slit gap parameter.
        """
        return (self._last_update.alarm_severity, self._last_update.alarm_status)

    def validate(self, drivers):
        """
        Perform validation of this parameter returning a list of errors.

        Args:
            drivers (list[ReflectometryServer.ioc_driver.IocDriver]): list of driver to help with validation

        Returns:
            (list[str]): list of problems; Empty list if there are no errors

        """
        return []

    def _on_is_changing_change(self, _):
        """
        Trigger an update for the is_changing status of this parameter on such an event in the PV wrapper.

        Args:
            update (ReflectometryServer.pv_wrapper.IsChangingUpdate): The update event
        """
        self._on_update_changing_state(None)

    @property
    def is_changing(self):
        """
        Returns: Is the parameter changing (displacing)
        """
        return self._pv_wrapper.is_moving
