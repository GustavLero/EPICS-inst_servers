"""
Test data and classes.
"""
from utils import DEFAULT_TEST_TOLERANCE

from ReflectometryServer.beamline import BeamlineMode, Beamline
from ReflectometryServer.components import Component, TiltingComponent, ThetaComponent
from ReflectometryServer.geometry import PositionAndAngle
from ReflectometryServer.ioc_driver import DisplacementDriver, AngleDriver
from ReflectometryServer.parameters import BeamlineParameter, TrackingPosition, AngleParameter
from time import time

class EmptyBeamlineParameter(BeamlineParameter):
    """
    A Bemline Parameter Stub. Counts the number of time it is asked to move
    """
    def __init__(self, name):
        super(EmptyBeamlineParameter, self).__init__(name)
        self.move_component_count = 0

    def _check_and_move_component(self):
        self.move_component_count += 1

    def validate(self, drivers):
        return []


class DataMother(object):
    """
    Test data for various tests.
    """
    BEAMLINE_MODE_NEUTRON_REFLECTION = BeamlineMode(
        "Neutron reflection",
        ["slit2height", "height", "theta", "detectorheight"])

    BEAMLINE_MODE_EMPTY = BeamlineMode("Empty", [])

    @staticmethod
    def beamline_with_3_empty_parameters():
        """

        Returns: a beamline with three empty parameters, all in a mode

        """
        one = EmptyBeamlineParameter("one")
        two = EmptyBeamlineParameter("two")
        three = EmptyBeamlineParameter("three")
        beamline_parameters = [one, two, three]
        mode = BeamlineMode("all", [beamline_parameter.name for beamline_parameter in beamline_parameters])
        naught_and_two = BeamlineMode("components1and3", [beamline_parameters[0].name, beamline_parameters[2].name])
        two = BeamlineMode("just2", [beamline_parameters[2].name])

        beamline = Beamline([], beamline_parameters, [], [mode, naught_and_two, two])

        beamline.active_mode = mode.name

        return beamline_parameters, beamline

    @staticmethod
    def beamline_s1_s3_theta_detector(spacing):
        """
        Create beamline with Slits 1 and 3 a theta and a detector
        Args:
            spacing: spacing between components

        Returns: beamline, axes

        """
        # components
        s1 = Component("s1_comp", PositionAndAngle(0.0, 1 * spacing, 90))
        s3 = Component("s3_comp", PositionAndAngle(0.0, 3 * spacing, 90))
        detector = TiltingComponent("Detector_comp", PositionAndAngle(0.0, 4 * spacing, 90))
        theta = ThetaComponent("ThetaComp_comp", PositionAndAngle(0.0, 2 * spacing, 90), [detector])
        comps = [s1, theta, s3, detector]
        # BEAMLINE PARAMETERS
        slit1_pos = TrackingPosition("s1", s1, True)
        slit3_pos = TrackingPosition("s3", s3, True)
        theta_ang = AngleParameter("theta", theta, True)
        detector_position = TrackingPosition("det", detector, True)
        detector_angle = AngleParameter("det_angle", detector, True)
        params = [slit1_pos, theta_ang, slit3_pos, detector_position, detector_angle]
        # DRIVES
        s1_axis = create_mock_axis("MOT:MTR0101", 0, 1)
        s3_axis = create_mock_axis("MOT:MTR0102", 0, 1)
        det_axis = create_mock_axis("MOT:MTR0104", 0, 1)
        det_angle_axis = create_mock_axis("MOT:MTR0105", 0, 1)
        axes = {"s1_axis": s1_axis,
                  "s3_axis": s3_axis,
                  "det_axis": det_axis,
                  "det_angle_axis": det_angle_axis}
        drives = [DisplacementDriver(s1, s1_axis),
                  DisplacementDriver(s3, s3_axis),
                  DisplacementDriver(detector, det_axis),
                  AngleDriver(detector, det_angle_axis)]
        # MODES
        nr_inits = {}
        nr_mode = BeamlineMode("NR", [param.name for param in params], nr_inits)
        disabled_mode = BeamlineMode("DISABLED", [param.name for param in params], nr_inits, is_disabled=True)
        modes = [nr_mode, disabled_mode]
        beam_start = PositionAndAngle(0.0, 0.0, 0.0)
        bl = Beamline(comps, params, drives, modes, beam_start)
        bl.active_mode = nr_mode.name
        return bl, axes


def create_mock_axis(name, init_position, max_velocity):
    """
    Create a mock axis
    Args:
        name: pv name of axis
        init_position: initial position
        max_velocity: maximum velocity of the axis

    Returns:
            mocked axis
    """

    return MockMotorPVWrapper(name, init_position, max_velocity)


class MockMotorPVWrapper(object):
    def __init__(self, pv_name, init_position, max_velocity, is_vertical=True):
        self.name = pv_name
        self._value = init_position
        self.max_velocity = max_velocity
        self.velocity = None
        self.resolution = DEFAULT_TEST_TOLERANCE
        self.after_rbv_change_listener = set()
        self.after_sp_change_listener = set()
        self.after_status_change_listener = set()
        self.after_velocity_change_listener = set()
        self.is_vertical = is_vertical

    def initialise(self):
        pass

    def add_after_rbv_change_listener(self, listener):
        self.after_rbv_change_listener.add(listener)

    def add_after_sp_change_listener(self, listener):
        self.after_sp_change_listener.add(listener)

    def add_after_status_change_listener(self, listener):
        self.after_status_change_listener.add(listener)

    def add_after_velocity_change_listener(self, listener):
        self.after_velocity_change_listener.add(listener)

    def initiate_move_with_change_of_velocity(self):
        pass

    @property
    def sp(self):
        return self._value

    @sp.setter
    def sp(self, new_value):
        self._value = new_value
        for listener in self.after_sp_change_listener:
            listener(new_value, None, None)
        for listener in self.after_rbv_change_listener:
            listener(new_value, None, None)

    @property
    def rbv(self):
        return self._value


class MockChannelAccess(object):
    def __init__(self, pvs):
        self._pvs = pvs

    def pv_exists(self, pv):
        return pv in self._pvs.keys()

    def add_monitor(self,pv, call_back_function):
        pass

    def caget(self, pv):
        try:
            return self._pvs[pv]
        except KeyError:
            return None

    def caput(self, pv, value):
        self._pvs[pv] = value