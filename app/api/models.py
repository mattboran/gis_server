import json
from typing import List, Tuple, Optional
from functools import cached_property

import numpy as np
import peewee as pw
from geopy import Point
from geopy.distance import great_circle
from shapely.geometry import Polygon

from api.db import db
from api.geometry import minimum_bounding_rectangle

CoordinateList = List[Tuple[float, float]]


class CoordinateListField(pw.TextField):
    def db_value(self, value: CoordinateList) -> str:
        return json.dumps(value)

    def python_value(self, value) -> CoordinateList:
        return json.loads(value)


class Bucket(pw.Model):
    region = pw.TextField(primary_key=True)
    extent = CoordinateListField()
    n_grid = pw.IntegerField()

    def index_for_coordinate(self, coord: Tuple[float, float]) -> Optional[int]:
        cols = np.linspace(self.extent[0][0], self.extent[1][0], num=self.n_grid)
        rows = np.linspace(self.extent[0][1], self.extent[1][1], num=self.n_grid)
        col = np.searchsorted(cols, coord[0])
        row = np.searchsorted(rows, coord[1])
        idx = col + self.n_grid * (row - 1)
        idx = idx if idx > 0 else None
        return idx

    def indices_surrounding_coordinate(self, coord: Tuple[float, float]) -> List[int]:
        cols = np.linspace(self.extent[0][0], self.extent[1][0], num=self.n_grid)
        rows = np.linspace(self.extent[0][1], self.extent[1][1], num=self.n_grid)
        col = np.searchsorted(cols, coord[0])
        row = np.searchsorted(rows, coord[1])
        indices = []
        for r in range(row-1, row+2):
            for c in range(col-1, col+2):
                indices.append(c + self.n_grid * (r - 1))
        return [idx for idx in indices if idx >= 0]

    class Meta:
        database = db


class Address(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField()
    building_type = pw.TextField(null=True)
    address_1 = pw.TextField(null=True) # TODO: - IntegerField
    address_2 = pw.TextField(null=True)
    predirective = pw.TextField(null=True)
    postdirective = pw.TextField(null=True)
    street_name = pw.TextField(null=True)
    post_type = pw.TextField(null=True)
    unit_type = pw.TextField(null=True)
    unit_identifier = pw.TextField(null=True)
    full_address = pw.TextField()
    coord = CoordinateListField()
    bucket_idx = pw.IntegerField(null=True)
    building_idx = pw.IntegerField(null=True)
    street_idx = pw.IntegerField(null=True)

    @property
    def center(self) -> Tuple[float, float]:
        return self.coord[0]

    class Meta:
        database = db


class Building(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)
    height = pw.IntegerField(null=True)
    ground_elevation = pw.IntegerField(null=True)
    building_type = pw.TextField(null=False)
    polygon_points = CoordinateListField(null=False)
    bucket_idx = pw.IntegerField(null=True)
    # TODO: - This can probably be removed
    address_idx = pw.IntegerField(null=True)

    @staticmethod
    def get_buildings_for_bucket_indices(indices):
        return (Building.select(Building.idx, Building.polygon_points, Building.height,
                                Building.ground_elevation, Building.building_type,
                                Address.full_address, Address.coord)
                        .join(Address, attr='address', on=(Building.idx==Address.building_idx))
                        .where(Building.bucket_idx << indices))

    @cached_property
    def center(self) -> Tuple[float, float]:
        min_x, min_y, max_x, max_y = self.bbox
        result_x = (min_x + max_x) / 2.0
        result_y = (min_y + max_y) / 2.0
        return result_x, result_y

    @cached_property
    def bbox(self) -> Tuple[float, float, float, float]:
        min_x, min_y = 100000.0, 100000.0
        max_x, max_y = -100000.0, -100000.0
        for point in self.polygon_points:
            x, y = point
            min_x = min(x, min_x)
            max_x = max(x, max_x)
            min_y = min(y, min_y)
            max_y = max(y, max_y)
        return min_x, min_y, max_x, max_y

    @cached_property
    def lines_for_shape(self) -> List[Tuple[np.array, np.array]]:
        points = np.array(self.polygon_points).T
        return [(points[:,i], points[:,i+1]) for i in range(points.shape[1]-1)]

    @cached_property
    def xy_extent_in_meters(self) -> np.array:
        min_x, min_y, max_x, max_y = self.bbox
        origin = Point(latitude=min_y, longitude=min_x)
        max_x_point = Point(latitude=min_y, longitude=max_x)
        max_y_point = Point(latitude=max_y, longitude=min_x)
        x_distance = great_circle(origin, max_x_point).meters
        y_distance = great_circle(origin, max_y_point).meters
        return np.array((x_distance, y_distance))

    @cached_property
    def origin(self) -> Tuple[float, float]:
        x, y, _, _ = self.bbox
        return x, y

    @cached_property
    def points_in_local_coords(self) -> List[Tuple[float, float]]:
        min_x, min_y, max_x, max_y = self.bbox
        min_point = np.array((min_x, min_y))
        max_point = np.array((max_x, max_y))
        extent = max_point - min_point
        indep_var = (np.array(self.polygon_points) - min_point) / extent
        res = indep_var * self.xy_extent_in_meters
        return [tuple(x) for x in res]

    @cached_property
    def simplified_polygon(self) -> CoordinateList:
        points = Polygon(self.polygon_points)
        if len(self.polygon_points) > 15:
            min_x, min_y, max_x, max_y = self.bbox
            tolerance = min((max_x - min_x), (max_y - min_y)) / 5.0
            return points.simplify(tolerance, preserve_topology=False)
        return points

    @cached_property
    def min_bounding_rect(self) -> CoordinateList:
        return minimum_bounding_rectangle(self.polygon_points)

    class Meta:
        database = db


class Street(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)
    l_min_addr = pw.IntegerField(null=True)
    l_max_addr = pw.IntegerField(null=True)
    r_min_addr = pw.IntegerField(null=True)
    r_max_addr = pw.IntegerField(null=True)
    prefix = pw.TextField(null=True)
    name = pw.TextField()
    street_type = pw.TextField(null=True)
    suffix = pw.TextField(null=True)
    full_name = pw.TextField()
    coords = CoordinateListField()

    class Meta:
        database = db