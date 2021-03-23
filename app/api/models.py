import json
from typing import List, Tuple
from functools import cached_property

import numpy as np
import peewee as pw

from api.db import db
from api.geometry import minimum_bounding_rectangle, sorted_points_by_polar_angle

CoordinateList = List[Tuple[float, float]]


class CoordinateListField(pw.TextField):
    def db_value(self, value: CoordinateList) -> str:
        return json.dumps(value)

    def python_value(self, value) -> CoordinateList:
        return json.loads(value)


class IndexListField(pw.TextField):
    def db_value(self, value: List[int]) -> str:
        return json.dumps(value)

    def python_value(self, value) -> List[int]:
        return json.loads(value)


class Address(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField()
    building_type = pw.TextField(null=True)
    address_1 = pw.TextField(null=True)
    address_2 = pw.TextField(null=True)
    predirective = pw.TextField(null=True)
    postdirective = pw.TextField(null=True)
    street_name = pw.TextField(null=True)
    post_type = pw.TextField(null=True)
    unit_type = pw.TextField(null=True)
    unit_identifier = pw.TextField(null=True)
    full_address = pw.TextField()
    coord = CoordinateListField()

    @staticmethod
    def all(region: str) -> List:
        return list(Address.select().where(Address.region == region))

    @property
    def center(self) -> Tuple[float, float]:
        return self.coord[0]

    @property
    def full_address_with_region(self) -> str:
        return self.full_address_without_region + ", " + f"{self.region}".capitalize()

    @property
    def full_address_without_region(self) -> str:
        components = [self.address_1, self.predirective, self.street_name, self.post_type]
        return " ".join([c for c in components if c])

    class Meta:
        database = db


class Building(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)
    height = pw.IntegerField(null=True)
    ground_elevation = pw.IntegerField(null=True)
    building_type = pw.TextField(null=False)
    polygon_points = CoordinateListField(null=False)
    dob_id = pw.TextField(null=True) 

    @staticmethod
    def all(region=None) -> List:
        return list(Building.select().where(Building.region == region))

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
        points = np.array(self.min_bounding_rect).T
        return [(points[:,i], points[:,i+1]) for i in range(points.shape[1]-1)]

    @cached_property
    def min_bounding_rect(self) -> CoordinateList:
        rect = minimum_bounding_rectangle(self.polygon_points)
        return sorted_points_by_polar_angle(rect, self.center)

    class Meta:
        database = db
