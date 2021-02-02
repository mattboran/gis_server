import logging
from typing import Tuple, List, Union, Optional
import sys

import geopy
import geopy.distance
import numpy as np

LAT_LON_TO_M = 111_139.0
FT_TO_M = 0.3048

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

def minimum_bounding_rectangle(points):
    """
    Find the smallest bounding rectangle for a set of points. These
    points should already be a convex hull
    Returns a set of points representing the corners of the bounding box.

    :param points: an nx2 matrix of coordinates
    :rval: an nx2 matrix of coordinates
    """
    pi2 = np.pi / 2.0
    hull_points = np.array(points)

    # calculate edge angles
    edges = np.zeros((len(hull_points)-1, 2))
    edges = hull_points[1:] - hull_points[:-1]

    angles = np.zeros((len(edges)))
    angles = np.arctan2(edges[:, 1], edges[:, 0])

    angles = np.abs(np.mod(angles, pi2))
    angles = np.unique(angles)

    # find rotation matrices
    rotations = np.vstack([
        np.cos(angles),
        np.cos(angles-pi2),
        np.cos(angles+pi2),
        np.cos(angles)]).T
    rotations = rotations.reshape((-1, 2, 2))

    # apply rotations to the hull
    rot_points = np.dot(rotations, hull_points.T)

    # find the bounding points
    min_x = np.nanmin(rot_points[:, 0], axis=1)
    max_x = np.nanmax(rot_points[:, 0], axis=1)
    min_y = np.nanmin(rot_points[:, 1], axis=1)
    max_y = np.nanmax(rot_points[:, 1], axis=1)

    # find the box with the best area
    areas = (max_x - min_x) * (max_y - min_y)
    best_idx = np.argmin(areas)

    # return the best box
    x1 = max_x[best_idx]
    x2 = min_x[best_idx]
    y1 = max_y[best_idx]
    y2 = min_y[best_idx]
    r = rotations[best_idx]

    rval = np.zeros((4, 2))
    rval[2] = np.dot([x1, y2], r)
    rval[1] = np.dot([x2, y2], r)
    rval[0] = np.dot([x2, y1], r)
    rval[3] = np.dot([x1, y1], r)
    return rval

def length_in_meters(v1, v2) -> float:
    p1 = geopy.Point(latitude=v1[1], longitude=v1[0])
    p2 = geopy.Point(latitude=v2[1], longitude=v2[0])
    dist = geopy.distance.great_circle(p1, p2).meters
    logger.info("v1: %s, v2: %s, dist: %s", v1, v2, dist)
    return dist

def sorted_points_by_polar_angle(points: np.array, origin: np.array) -> np.array:
    """
    Sorts `points` by polar angle with respect to origin

    Returns:
        points, but sorted by polar angle.
    """
    origin = np.array(origin)
    points = points.T
    origins = np.array([origin,]*points.shape[1]).T
    vectors = points - origins
    angles = np.arctan2(vectors[0,], vectors[1,]) + np.pi
    points_with_angles = np.vstack((points, angles))
    sorted_points_with_angles = points_with_angles[:, points_with_angles[2,].argsort()]
    return sorted_points_with_angles[:2,].T

class Ray:

    def __init__(self, loc: Tuple[float, float], heading: float):
        """
        Initialize a ray centered at the viewer, with normalized
        direction based on heading in a lat/lon coordinate system.
        """
        self.ro = np.array(loc)

        start = geopy.Point(loc[1], loc[0])
        d = geopy.distance.distance(kilometers=1)
        point = d.destination(point=start, bearing=heading)
        np_point = np.array([point.longitude, point.latitude])
        locs = np.vstack((loc, np_point)).T

        rd = locs[:,1] - locs[:,0]
        magnitude = np.sqrt(np.dot(rd, rd))
        self.rd = rd / magnitude

    def point_at(self, t: float) -> np.array:
        """
        Get the coordinate at `t` along the ray.
        """
        return self.ro + t * self.rd

    def line_intersection(self, line: Tuple[np.array, np.array]) -> Optional[Tuple[float, np.array, np.array, float]]:
        """
        Perform intersection test between self and `line`

        Returns:
            float: t if intersection, else None
        """
        l1, l2 = line
        v1 = self.ro - l1
        v2 = l2 - l1
        v3 = np.array([-self.rd[1], self.rd[0]])
        dot = np.dot(v2, v3)
        if not np.any(dot):
            return None
        t1 = np.cross(v2, v1) / dot
        t2 = np.dot(v1, v3) / dot
        if t1 >= 0.0 and 0.0 <= t2 <= 1.0:
            dxdy = v2
            norm = np.array((-dxdy[1], dxdy[0]))
            if np.dot(norm, self.rd) > 0:
                norm = np.array((dxdy[1], -dxdy[0]))
            length = np.linalg.norm(norm, ord=1)
            if length != 0:
                normalized = norm / length
            else:
                res = [0.0, 0.0]
                res[np.argmax(norm)] = 1.0
                normalized = np.array(res)
            midpoint = (l1 + l2) / 2.0
            return t1, midpoint, normalized, length_in_meters(l2, l1)
        return None