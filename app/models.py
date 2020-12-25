import json
from typing import List, Tuple, Union

import numpy as np
import peewee as pw

from db import db

CoordinateList = List[Tuple[float, float]]

class CoordinateListField(pw.TextField):
    def db_value(self, value: CoordinateList) -> str:
        return json.dumps(value)

    def python_value(self, value) -> CoordinateList:
        return json.loads(value)


class Bucket(pw.Model):
    region = pw.TextField(primary_key=True)
    extent = CoordinateListField(null=False)
    n_grid = pw.IntegerField(null=False)

    def index_for_coordinate(self, coord: Tuple[float, float]) -> Union[int, None]:
        cols = np.linspace(self.extent[0][0], self.extent[1][0], num=self.n_grid)
        rows = np.linspace(self.extent[0][1], self.extent[1][1], num=self.n_grid)
        col = np.searchsorted(cols, coord[0])
        row = np.searchsorted(rows, coord[1])
        idx = col + self.n_grid * (row - 1)
        idx = idx if idx > 0 else None
        return idx

    class Meta:
        database = db


class Address(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)
    building_type = pw.TextField(null=True)
    address_1 = pw.TextField(null=True)
    address_2 = pw.TextField(null=True)
    predirective = pw.TextField(null=True)
    postdirective = pw.TextField(null=True)
    street_name = pw.TextField(null=True)
    post_type = pw.TextField(null=True)
    unit_type = pw.TextField(null=True)
    unit_identifier = pw.TextField(null=True)
    full_address = pw.TextField(null=False)
    coord = CoordinateListField(null=False)

    @property
    def center(self):
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
    bucket_id = pw.IntegerField(null=True)
    address_idx = pw.ForeignKeyField(Address, backref='address', null=True)

    @property
    def center(self):
        min_x, min_y, max_x, max_y = self.bbox
        result_x = (min_x + max_x) / 2.0
        result_y = (min_y + max_y) / 2.0
        return result_x, result_y

    @property
    def bbox(self):
        min_x, min_y = 100000.0, 100000.0
        max_x, max_y = -100000.0, -100000.0
        for point in self.polygon_points:
            x, y = point
            min_x = min(x, min_x)
            max_x = max(x, max_x)
            min_y = min(y, min_y)
            max_y = max(y, max_y)
        return min_x, min_y, max_x, max_y

    @property
    def lines_for_shape(self):
        points = np.array(self.polygon_points).T
        return [(points[:,i], points[:,i+1]) for i in range(points.shape[1]-1)]

    class Meta:
        database = db