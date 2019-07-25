"""
The driving layer communicates between the component layer and underlying pvs.
"""

import math
import logging

from ReflectometryServer.engineering_corrections import NoCorrection
from ReflectometryServer.components import ChangeAxis

logger = logging.getLogger(__name__)


class IocDriver(object):
    """
    Drives an actual motor axis based on a component in the beamline model.
    """
    def __init__(self, component, axis, synchronised=True, engineering_correct=NoCorrection()):
        """
        Drive the IOC based on a component
        Args:
            component (ReflectometryServer.components.Component):
            axis (ReflectometryServer.pv_wrapper.MotorPVWrapper): The PV that this driver controls.
            synchronised (bool): If True then axes will set their velocities so they arrive at the end point at the same
                time; if false they will move at their current speed.
            engineering_correct (ReflectometryServer.engineering_corrections.EngineeringCorrection): the engineering
                correction to apply to the value from the component before it is sent to the pv.
        """
        self._engineering_correct = engineering_correct
        self._component = component
        self._axis = axis
        self._rbv_cache = self._engineering_correct.from_axis(self._axis.rbv)
        self._sp_cache = None
        self._synchronised = synchronised

        self._axis.add_after_rbv_change_listener(self._on_update_rbv)
        self._axis.add_after_sp_change_listener(self._on_update_sp)

    def __repr__(self):
        return "{} for axis pv {} and component {}".format(
            self.__class__.__name__, self._axis.name, self._component.name)

    def initialise(self):
        """
        Post monitors and read initial value from the axis.
        """
        self._axis.initialise()
        self.initialise_setpoint()

    def initialise_setpoint(self):
        """
        Initialise the setpoint beam model in the component layer with an initial value read from the motor axis.
        """
        raise NotImplemented()

    def is_for_component(self, component):
        """
        Does this driver use the component given.
        Args:
            component: the component to check

        Returns: True if this ioc driver uses the component; false otherwise
        """
        return component is self._component

    def _axis_will_move(self):
        """
        Returns: True if the axis set point has changed and it will move any distance
        """
        return not self.at_target_setpoint() and self._is_changed()

    def get_max_move_duration(self):
        """
        Returns: The maximum duration of the requested move for all associated axes. If axes are not synchornised this
        will return 0 but movement will still be required.
        """
        if self._axis_will_move() and self._synchronised:
            return self._get_distance() / self._axis.max_velocity
        else:
            return 0.0

    def perform_move(self, move_duration, force=False):
        """
        Tells the driver to perform a move to the component set points within a given duration.
        The axis will update the set point cache when it is changed so don't need to do it here

        Args:
            move_duration (float): The duration in which to perform this move
            force (bool): move even if component does not report changed
        """
        if self._axis_will_move() or force:
            logger.debug("Moving axis {} {}".format(self._axis.name, self._get_distance()))
            if move_duration > 1e-6 and self._synchronised:
                self._axis.initiate_move_with_change_of_velocity()
                self._axis.velocity = self._get_distance() / move_duration
            self._axis.sp = self._engineering_correct.to_axis(self._get_component_sp())
        self._clear_changed()

    def _is_changed(self):
        """
        Returns whether this driver's component has been flagged for change.
        """
        raise NotImplemented("This should be implemented in the subclass")

    def _clear_changed(self):
        """
        Clears the flag indicating whether this driver's component has been changed.
        """
        raise NotImplemented("This should be implemented in the subclass")

    def rbv_cache(self):
        """
        Return the last cached readback value of the underlying motor if one exists; throws an exception otherwise.

        Returns: The cached readback value for the motor
        """
        if self._rbv_cache is None:
            raise ValueError("Axis {} not initialised. Check configuration is correct and motor IOC is running."
                             .format(self._axis.name))
        return self._rbv_cache

    def _get_distance(self):
        """
        :return: The distance between the target component position and the actual motor position in y.
        """
        return math.fabs(self.rbv_cache() - self._get_component_sp())

    def _get_component_sp(self):
        """
        Returns: position that the component is set to
        """
        raise NotImplemented()

    def _on_update_rbv(self, new_value, alarm_severity, alarm_status):
        """
        Listener to trigger on a change of the readback value of the underlying motor.

        Args:
            new_value: new axis readback value that is given
            alarm_severity (server_common.channel_access.AlarmSeverity): severity of any alarm
            alarm_status (server_common.channel_access.AlarmCondition): the alarm status
        """
        corrected_new_value = self._engineering_correct.from_axis(new_value)
        self._rbv_cache = corrected_new_value
        self._propagate_rbv_change(corrected_new_value, alarm_severity, alarm_status)

    def _propagate_rbv_change(self, new_value, alarm_severity, alarm_status):
        """
        Signal that the motor readback value has changed to the middle component layer. Subclass must implement this
        method.

        Args:
            new_value: new axis value that is given
            alarm_severity (server_common.channel_access.AlarmSeverity): severity of any alarm
            alarm_status (server_common.channel_access.AlarmCondition): the alarm status
        """
        raise NotImplemented()

    def _on_update_sp(self, value, alarm_severity, alarm_status):
        """
        Updates the cached set point from the axis with a new value.
        Args:
            value: The new set point value.
        """
        self._sp_cache = self._engineering_correct.from_axis(value)

    def at_target_setpoint(self):
        """
        Returns: True if the setpoint on the component and the one on the motor PV are the same (within tolerance),
            False if they differ.
        """
        if self._sp_cache is None:
            return False

        difference = abs(self._get_component_sp() - self._sp_cache)
        return difference < self._axis.resolution


class DisplacementDriver(IocDriver):
    """
    Drives a component with linear displacement movement
    """
    def __init__(self, component, motor_axis, out_of_beam_position=None, tolerance_on_out_of_beam_position=1,
                 synchronised=True, engineering_correct=NoCorrection()):
        """
        Constructor.
        Args:
            component (ReflectometryServer.components.Component): The component providing the values for the axes
            motor_axis (ReflectometryServer.pv_wrapper.MotorPVWrapper): The PV that this driver controls.
            out_of_beam_position (float): this position that the component should be in when out of the beam; None for
                can not set the component to be out of the beam
            tolerance_on_out_of_beam_position (float): this the tolerance on the out of beam position, if the motor
                is within this tolerance of the out_of_beam_position it will read out of beam otherwise the position
            synchronised (bool): If True then axes will set their velocities so they arrive at the end point at the same
                time; if false they will move at their current speed.
            engineering_correct (ReflectometryServer.engineering_correction.EngineeringCorrection): the engineering
                correction to apply to the value from the component before it is sent to the pv.
        """
        super(DisplacementDriver, self).__init__(component, motor_axis, synchronised, engineering_correct)
        self._out_of_beam_position = out_of_beam_position
        self._tolerance_on_out_of_beam_position = tolerance_on_out_of_beam_position

    def _get_in_beam_status(self, value):
        if self._out_of_beam_position is not None:
            distance_to_out_of_beam = abs(value - self._out_of_beam_position)
            in_beam_status = distance_to_out_of_beam > self._tolerance_on_out_of_beam_position
        else:
            in_beam_status = True
        return in_beam_status

    def initialise_setpoint(self):
        """
        Initialise the setpoint beam model in the component layer with an initial value read from the motor axis.
        """
        sp = self._engineering_correct.from_axis(self._axis.sp)
        if self._out_of_beam_position is not None:
            self._component.beam_path_set_point.is_in_beam = self._get_in_beam_status(sp)
        self._component.beam_path_set_point.init_displacement_from_motor(sp)

    def _propagate_rbv_change(self, new_value, alarm_severity, alarm_status):
        """
        Propagate the new height readback value to the middle component layer.

        Args:
            new_value: new height readback value that is given
            alarm_severity (server_common.channel_access.AlarmSeverity): severity of any alarm
            alarm_status (server_common.channel_access.AlarmCondition): the alarm status
        """
        if self._out_of_beam_position is not None:
            self._component.beam_path_rbv.is_in_beam = self._get_in_beam_status(new_value)
        self._component.beam_path_rbv.set_displacement(new_value, alarm_severity, alarm_status)

    def _get_component_sp(self):
        if self._component.beam_path_set_point.is_in_beam:
            displacement = self._component.beam_path_set_point.get_displacement()
        else:
            if self._out_of_beam_position is None:
                displacement = 0
                logger.error("The component, {},is out of the beam but there is no out of beam position for the driver "
                             "running axis{}".format(self._component.name, self._axis.name))
            else:
                displacement = self._out_of_beam_position
        return displacement

    def has_out_of_beam_position(self):
        """
        Returns: True if this Displacement driver has out of beam position set; False otherwise.
        """
        return self._out_of_beam_position is not None

    def _component_changed(self):
        return self._component.read_changed_flag(ChangeAxis.POSITION)

    def _is_changed(self):
        """
        Returns whether this driver's component's position has been flagged for change.
        """
        return self._component.read_changed_flag(ChangeAxis.POSITION)

    def _clear_changed(self):
        """
        Clears the flag indicating whether the this driver's component's position has been changed.
        """
        self._component.set_changed_flag(ChangeAxis.POSITION, False)


class AngleDriver(IocDriver):
    """
    Drives a component that has variable angle.
    """
    def __init__(self, component, angle_axis, synchronised=True, engineering_correct=NoCorrection()):
        """
        Constructor.
        Args:
            component (ReflectometryServer.components.Component): Component providing the values for the axes
            angle_axis(ReflectometryServer.pv_wrapper.MotorPVWrapper): PV for the angle motor axis
            synchronised (bool): If True then axes will set their velocities so they arrive at the end point at the same
                time; if false they will move at their current speed.
            engineering_correct (ReflectometryServer.engineering_correction.EngineeringCorrection): the engineering
                correction to apply to the value from the component before it is sent to the pv.
        """
        super(AngleDriver, self).__init__(component, angle_axis, synchronised, engineering_correct)

    def initialise_setpoint(self):
        """
        Initialise the setpoint beam model in the component layer with an initial value read from the motor axis.
        """
        self._component.beam_path_set_point.init_angle_from_motor(self._engineering_correct.from_axis(self._axis.sp))

    def _propagate_rbv_change(self, new_value, alarm_severity, alarm_status):
        """
        Propagate the new angle readback value to the middle component layer.

        Args:
            new_value: new angle readback value that is given
            alarm_severity (CaChannel._ca.AlarmSeverity): severity of any alarm
            alarm_status (CaChannel._ca.AlarmCondition): the alarm status
        """
        self._component.beam_path_rbv.angle = new_value

    def _get_component_sp(self):
        return self._component.beam_path_set_point.angle

    def _is_changed(self):
        """
        Returns whether this driver's component angle has been flagged for change.
        """
        return self._component.read_changed_flag(ChangeAxis.ANGLE)

    def _clear_changed(self):
        """
        Clears the flag indicating whether the this driver's component's angle has been changed.
        """
        self._component.set_changed_flag(ChangeAxis.ANGLE, False)
