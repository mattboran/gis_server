import logging
from typing import Tuple, List, Union, Optional

import geopy
import geopy.distance
import numpy as np

from .models import Building, Address

Centerable = Union[Building, Address]

LAT_LON_TO_M = 111_139
FT_TO_M = 0.3048

logger = logging.getLogger(__name__)

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

    def line_intersection(self, line: Tuple[np.array, np.array]) -> Optional[float]:
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
            return t1
        return None


class GridPartition:

    def __init__(self, n: int, items: List[Centerable], extent: Union[np.array, None]=None):
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

    def partition(self) -> List[List[Centerable]]:
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

    def make_buckets(self, c: np.array, r: np.array) -> List[List[Centerable]]:
        """
        Helper method to create buckets out of items at indices created in
        the `partition` method.

        Args:
            c (array): column index of `self.item[i]`
            r (array): `r`: row index of `self.item[i]`
        """
        indices = c + self.n * (r - 1)
        buckets = [[] for _ in range(self.n**2)]
        for item, idx in zip(self.items, indices):
            buckets[idx].append(item)
            item.bucket_idx = idx
        logger.info("Created a grid of %s by %s", self.n, self.n)
        return buckets

    def index_for_col_row(self, col: int, row: int) -> Optional[int]:
        idx = col + self.n * (row - 1)
        return idx if idx >= 0 else None

    def index_for_coordinate(self, loc) -> Optional[int]:
        col, row = self.col_and_row_for_coordinate(loc)
        return self.index_for_col_row(col, row)

    def col_and_row_for_coordinate(self, loc) -> Tuple[int, int]:
        col = np.searchsorted(self.cols, loc[0])
        row = np.searchsorted(self.rows, loc[1])
        return col, row

    def get_items_in_bucket_for_coordinate(self, loc) -> List[Centerable]:
        idx = self.index_for_coordinate(loc)
        if idx:
            return self.buckets[idx]
        return []


class Consolidator:

    def __init__(self, buildings: List[Building], addresses: List[Address], n_grid=150):
        self.n = n_grid
        self.buildings_grid = GridPartition(n_grid, buildings)
        self.address_grid = GridPartition(n_grid, addresses, extent=self.buildings_grid.extent)

    @property
    def buildings(self) -> List[Centerable]:
        return self.buildings_grid.items

    @property
    def addresses(self) -> List[Centerable]:
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
