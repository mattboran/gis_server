from fastapi import APIRouter, Depends
import numpy as np

from .dependencies import get_token
from .models import Bucket, Building
from .geometry import Ray

router = APIRouter(dependencies=[Depends(get_token)])

@router.get('/')
def read_root():
    return {"hello": "world! this file is changed. again."}

@router.get('/bucket')
async def get_bucket(region: str, lat: float, lon: float):
    bucket = Bucket.get(Bucket.region == region)
    indices = bucket.indices_surrounding_coordinate((lon, lat))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    response = {
        'n_buildings': len(buildings),
        'buildings': [{'idx': b.idx, 'addr': b.address.full_address} for b in buildings]
    }
    return response

@router.get('/intersect')
async def get_intersection(region: str, lat: float, lon: float, heading: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    t_vals, indices = [], []
    ray = Ray((lon, lat), heading)
    for i, b in enumerate(buildings):
        isects = [ray.line_intersection(l) for l in b.lines_for_shape]
        ts = [t for t in isects if t]
        if len(ts) > 1:
            t_vals.append(min(ts))
            indices.append(i)
    pts = [ray.point_at(t) for t in sorted(t_vals)]
    result = []
    for i, index in enumerate(indices):
        result.append({
            'point': np.array2string(pts[i]),
            'building_idx': buildings[index].idx,
            'address': buildings[index].address.full_address
        })
    return {'intersections': result}
