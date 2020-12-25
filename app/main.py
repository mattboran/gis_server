from fastapi import FastAPI
import numpy as np

from models import Bucket, Building, Address
from geometry import Ray

app = FastAPI()

@app.get('/')
def read_root():
    return {"hello": "world! this file is changed. again."}

@app.get('/bucket')
def get_bucket(region: str, lat: float, lon: float):
    bucket = Bucket.get(Bucket.region == region)
    idx = bucket.index_for_coordinate((lon, lat))
    buildings = (Building.select(Building.idx, Address.full_address)
                         .join(Address, attr='address')
                         .where(Building.bucket_id == idx))
    response = {
        'n_buildings': len(buildings),
        'buildings': [{'idx': b.idx, 'addr': b.address.full_address} for b in buildings]
    }
    return response

@app.get('/intersect')
def get_intersection(region: str, lat: float, lon: float, heading: float):
    bucket = Bucket.get(Bucket.region == region)
    idx = bucket.index_for_coordinate((lon, lat))
    buildings = Building.select().where(Building.bucket_id == idx)
    t_vals, indices = [], []
    ray = Ray((lon, lat), heading)
    for i, b in enumerate(buildings):
        lines = b.lines_for_shape
        isects = [ray.line_intersection(l) for l in lines]
        ts = [t for t in isects if t]
        if len(ts) > 1:
            t_vals.append(min(ts))
            indices.append(i)
    pts = [ray.point_at(t) for t in sorted(t_vals)]
    result = []
    for i, index in enumerate(indices):
        building = buildings[index]
        result.append({
            'point': np.array2string(pts[i]),
            'building_idx': building.idx,
            'address': building.address_idx
        })
    return {'intersections': result}