"""
Components on a beam
"""
from ReflectometryServer.beam_path_calc import TrackingBeamPathCalc, BeamPathTiltingJaws, BeamPathCalcAngle
from ReflectometryServer.movement_strategy import LinearMovementCalc


class Component(object):
    """
    Base object for all components that can sit on a beam line
    """

    def __init__(self, name, setup):
        """
        Initializer.
        Args:
            name (str): name of the component
            setup (ReflectometryServer.movement_strategy.LinearSetup): initial setup for the component
        """
        self._name = name
        self._init_beam_path_calcs(setup)

    def _init_beam_path_calcs(self, setup):
        self._beam_path_set_point = TrackingBeamPathCalc(LinearMovementCalc(setup))
        self._beam_path_rbv = TrackingBeamPathCalc(LinearMovementCalc(setup))

    @property
    def name(self):
        """
        Returns: Name of the component
        """
        return self._name

    @property
    def beam_path_set_point(self):
        """
        The beam path calculation for the set points. This is readonly and can only be set during construction
        Returns: beam path calculation for set points

        """
        return self._beam_path_set_point

    @property
    def beam_path_rbv(self):
        """
        The beam path calculation for the read backs. This is readonly and can only be set during construction
        Returns: beam path calculation for read backs
        """
        return self._beam_path_rbv


class TiltingJaws(Component):
    """
    Jaws which can tilt.
    """

    def __init__(self, name, setup):
        """
        Initializer.
        Args:
            name (str): name of the component
            setup (ReflectometryServer.movement_strategy.LinearSetup): initial setup for the component
        """
        super(TiltingJaws, self).__init__(name, setup)

    def _init_beam_path_calcs(self, setup):
        self._beam_path_set_point = BeamPathTiltingJaws(LinearMovementCalc(setup))
        self._beam_path_rbv = BeamPathTiltingJaws(LinearMovementCalc(setup))


class ReflectingComponent(Component):
    """
    Components which reflects the beam from an reflecting surface at an angle.
    """
    def __init__(self, name, setup):
        """
        Initializer.
        Args:
            name (str): name of the component
            setup (ReflectometryServer.movement_strategy.LinearSetup): initial setup for the component
        """
        super(ReflectingComponent, self).__init__(name, setup)

    def _init_beam_path_calcs(self, setup):
        self._beam_path_set_point = BeamPathCalcAngle(LinearMovementCalc(setup))
        self._beam_path_rbv = BeamPathCalcAngle(LinearMovementCalc(setup))

# class Bench(Component):
#     """
#     Jaws which can tilt.
#     """
#     def __init__(self, name, centre_of_rotation_z, distance_from_sample_to_bench):
#
#         super(Bench, self).__init__(name, ArcMovement(centre_of_rotation_z))
#         self.distance_from_sample_to_bench = distance_from_sample_to_bench
#
#     def calculate_front_position(self):
#         """
#         Returns: the angle to tilt so the jaws are perpendicular to the beam.
#         """
#         center_of_rotation = self.calculate_beam_interception()
#         x = center_of_rotation.z + self.distance_from_sample_to_bench * cos(self.incoming_beam.angle)
#         y = center_of_rotation.y + self.distance_from_sample_to_bench * sin(self.incoming_beam.angle)
#         return Position(y, x)
