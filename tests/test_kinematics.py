from app.services.kinematics import range_of_motion, three_point_angle


def test_three_point_angle_right_angle():
    assert three_point_angle((1, 0), (0, 0), (0, 1)) == 90


def test_three_point_angle_straight_angle():
    assert three_point_angle((-1, 0), (0, 0), (1, 0)) == 180


def test_range_of_motion():
    assert range_of_motion([4.2, 61.4, 20]) == (4.2, 61.4, 57.2)
