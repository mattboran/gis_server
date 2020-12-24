import json
from typing import List, Tuple

import peewee as pw


CoordinateList = List[Tuple[float, float]]

class CoordinateListField(pw.TextField):
    def db_value(self, value: CoordinateList) -> str:
        return json.dumps(value)

    def python_value(self, value) -> CoordinateList:
        return json.loads(value)

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


class Bucket(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)


class Building(pw.Model):
    idx = pw.IntegerField(primary_key=True)
    region = pw.TextField(null=False)
    height = pw.IntegerField(null=True)
    ground_elevation = pw.IntegerField(null=True)
    building_type = pw.TextField(null=False)
    polygon_points = CoordinateListField(null=False)
    address_idx = pw.ForeignKeyField(Address, backref='address', null=True)
    bucket_id = pw.ForeignKeyField(Bucket, backref='bucket', null=True)

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


