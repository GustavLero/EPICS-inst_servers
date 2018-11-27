from ReflectometryServer.beamline import Beamline, BeamlineMode
from ReflectometryServer.components import Component, ReflectingComponent
from ReflectometryServer.movement_strategy import LinearSetup
from ReflectometryServer.geometry import PositionAndAngle
from ReflectometryServer.parameters import Theta


def create_beamline():
    """

    Returns: example beamline

    """
    perp_to_floor = 90.0
    beam_start = PositionAndAngle(y=0, z=0, angle=-2.5)
    s0 = Component("s0", setup=LinearSetup(0, 0, perp_to_floor))
    s1 = Component("s1", setup=LinearSetup(0, 1, perp_to_floor))
    frame_overlap_mirror = ReflectingComponent("FOM", setup=LinearSetup(0, 2, perp_to_floor))
    frame_overlap_mirror.beam_path_set_point.enabled = False
    polarising_mirror = ReflectingComponent("Polarising mirror", setup=LinearSetup(0, 3, perp_to_floor))
    polarising_mirror.beam_path_set_point.enabled = False
    s2 = Component("s2", setup=LinearSetup(0, 4, perp_to_floor))
    ideal_sample_point = ReflectingComponent("Ideal Sample Point", setup=LinearSetup(0, 5, perp_to_floor))
    s3 = Component("s3", setup=LinearSetup(0, 6, perp_to_floor))
    analyser = ReflectingComponent("analyser", setup=LinearSetup(0, 7, perp_to_floor))
    analyser.beam_path_set_point.enabled = False
    s4 = Component("s4", setup=LinearSetup(0, 8, perp_to_floor))
    detector = Component("detector", setup=LinearSetup(0, 10, perp_to_floor))

    theta = Theta("theta", ideal_sample_point)
    nr_mode = BeamlineMode("NR", ["theta"])
    beamline = Beamline(
        [s0, s1, frame_overlap_mirror, polarising_mirror, s2, ideal_sample_point, s3, analyser, s4, detector],
        [theta],
        [],
        [nr_mode], beam_start)

    beamline.active_mode = nr_mode.name

    return beamline


def generate_theta_movement():
    beamline = create_beamline()
    positions_z = [component.calculate_beam_interception().z for component in beamline]
    positions_z.insert(0, "z position")
    positions = [
        positions_z,
    ]
    for theta in range(0, 20, 1):
        beamline.parameter("theta").sp_move = theta * 1.0
        positions_y = [component.calculate_beam_interception().y for component in beamline]
        positions_y.insert(0, "theta {}".format(theta))
        positions.append(positions_y)

    beamline[3].beam_path_set_point.enabled = True
    sm_angle = 5
    beamline[3].beam_path_set_point.angle = sm_angle
    for theta in range(0, 20, 1):
        beamline.parameter("theta").sp_move = theta * 1.0
        positions_y = [component.calculate_beam_interception().y for component in beamline]
        positions_y.insert(0, "theta {} sman{}".format(theta, sm_angle))
        positions.append(positions_y)

    return positions


if __name__ == '__main__':
    thetas = generate_theta_movement()

    with open("example.csv", mode="w") as f:
        for theta in thetas:
            f.write(", ".join([str(v) for v in theta]))
            f.write("\n")
