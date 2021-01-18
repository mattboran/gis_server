import logging
from typing import Tuple, List, Union, Optional

import geopy
import geopy.distance
import numpy as np

LAT_LON_TO_M = 111_139.0
FT_TO_M = 0.3048

logger = logging.getLogger(__name__)

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
    rval[0] = np.dot([x1, y2], r)
    rval[1] = np.dot([x2, y2], r)
    rval[2] = np.dot([x2, y1], r)
    rval[3] = np.dot([x1, y1], r)
    return rval

def length_in_meters(v1, v2) -> float:
    p1 = geopy.Point(latitude=v1[1], longitude=v1[0])
    p2 = geopy.Point(latitude=v2[1], longitude=v2[0])
    return geopy.distance.great_circle(p1, p2).meters


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

    def line_intersection(self, line: Tuple[np.array, np.array]) -> Optional[Tuple[float, np.array, float]]:
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
            return t1, normalized, length_in_meters(l2, l1)
        return None


class GridPartition:

    def __init__(self, n: int, items: List, extent: Union[np.array, None]=None):
        self.n = n
        self.items = items
        centers = [item.center for item in items]
        self.centers: List[np.array] = np.array(centers).T
        if np.any(extent):
            self.extent = extent
        else:
            self.extent = self.get_item_extent()
        self.buckets = self.partition()

    def get_item_extent(self, delta: float=0.005) -> np.array:
        min_x = np.min(self.centers[0,])
        max_x = np.max(self.centers[0,])
        min_y = np.min(self.centers[1,])
        max_y = np.max(self.centers[1,])
        x_delta = abs(max_x - min_x)
        y_delta = abs(max_y - min_y)
        extent = (min_x - x_delta * delta,
                  max_x + x_delta * delta,
                  min_y - y_delta * delta,
                  max_y + y_delta * delta)
        return np.array(extent)

    def partition(self) -> List[List]:
        """
        Partition `self.items` into an `n` by `n` grid of buckets,
        where each bucket has some `items` in it.
        """
        cols = np.linspace(self.extent[0], self.extent[1], num=self.n)
        rows = np.linspace(self.extent[2], self.extent[3], num=self.n)
        self.cols = cols
        self.rows = rows
        c_cols = np.searchsorted(cols, self.centers[0,])
        c_rows = np.searchsorted(rows, self.centers[1,])
        return self.make_buckets(c_cols, c_rows)

    def make_buckets(self, c: np.array, r: np.array) -> List[List]:
        """
        Helper method to create buckets out of items at indices created in
        the `partition` method.

        Args:
            c (array): column index of `self.item[i]`
            r (array): `r`: row index of `self.item[i]`
        """
        indices = c + self.n * r
        buckets = [[] for _ in range(self.n**2)]
        for item, idx in zip(self.items, indices):
            buckets[idx].append(item)
            item.bucket_idx = idx
        logger.info("Created a grid of %s by %s", self.n, self.n)
        return buckets

    def index_for_col_row(self, col: int, row: int) -> Optional[int]:
        idx = col + self.n * row
        return idx if idx >= 0 else None

    def index_for_coordinate(self, loc) -> Optional[int]:
        col, row = self.col_and_row_for_coordinate(loc)
        return self.index_for_col_row(col, row)

    def col_and_row_for_coordinate(self, loc) -> Tuple[int, int]:
        col = np.searchsorted(self.cols, loc[0])
        row = np.searchsorted(self.rows, loc[1])
        return col, row

    def get_items_in_bucket_for_coordinate(self, loc) -> List:
        idx = self.index_for_coordinate(loc)
        if idx:
            return self.buckets[idx]
        return []


class Consolidator:

    def __init__(self, buildings, addresses, n_grid=150):
        self.n = n_grid
        self.buildings_grid = GridPartition(n_grid, buildings)
        self.address_grid = GridPartition(n_grid, addresses, extent=self.buildings_grid.extent)

    @property
    def buildings(self) -> List:
        return self.buildings_grid.items

    @property
    def addresses(self) -> List:
        return self.address_grid.items

    def consolidate(self):
        def distances_to_loc(centers, loc):
            locs = np.array([loc,] * centers.shape[1])
            distances = np.sum((centers - locs.T)**2, axis=0)
            return np.sqrt(distances)

        for i in range(len(self.buildings_grid.buckets)):
            if i % 100 == 0:
                logger.info("Processed %s buckets", i)
            shape_bucket = self.buildings_grid.buckets[i]
            address_bucket = self.address_grid.buckets[i]
            if not shape_bucket or not address_bucket:
                continue

            addresses_for_building = [[] for _ in shape_bucket]
            for j, address in enumerate(address_bucket):
                point = np.array(address.center)
                centers = np.array([b.center for b in shape_bucket]).T
                ds = distances_to_loc(centers, point)
                addresses_for_building[np.argmin(ds)].append(j)
            addr_indices = [addresses_for_building[i] for i in range(len(shape_bucket))]
            for j, building in enumerate(shape_bucket):
                indices = addr_indices[j]
                if indices:
                    building.address_idx = address_bucket[indices[0]].idx
                    for k in indices:
                        address_bucket[k].building_idx = building.idx
