from typing import List, Dict, Tuple, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import api.geometry as geom
from .dependencies import get_token
from .models import Bucket, Building, CoordinateList

router = APIRouter(dependencies=[Depends(get_token)])

class PointOut(BaseModel):
    latitude: float
    longitude: float


class BucketOut(BaseModel):
    idx: int
    address: str
    height: Optional[float]
    ground_elevation: Optional[float]
    building_type: Optional[str]
    center: PointOut
    polygon: List[PointOut]


class BucketResult(BaseModel):
    count: int
    result: List[BucketOut]


class IntersectionResult(BaseModel):
    idx: int
    t: float
    dist: float
    address: str
    point: PointOut


class IntersectionOut(BaseModel):
    count: int
    result: List[IntersectionResult]


def point_to_dict(point: Tuple[float, float]) -> Dict[str, float]:
    return {'latitude': point[1], 'longitude': point[0]}

def points_to_dict(points: CoordinateList) -> List[Dict[str, float]]:
    return [point_to_dict(p) for p in points]

@router.get('/bucket', response_model=BucketResult)
async def get_bucket(region: str, lat: float, lon: float):
    bucket = Bucket.get(Bucket.region == region)
    indices = bucket.indices_surrounding_coordinate((lon, lat))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    result = []
    for b in buildings:
        result.append({
            'idx': b.idx,
            'address': b.address.full_address,
            'center': point_to_dict(b.address.coord[0]),
            'polygon': points_to_dict(b.polygon_points)
        })
    return {
        'count': len(result),
        'result': result
    }

@router.get('/intersect', response_model=IntersectionOut)
async def get_intersection(region: str, lat: float, lon: float, heading: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    t_vals, indices = [], []
    ray = geom.Ray((lon, lat), heading)
    for i, b in enumerate(buildings):
        isects = [ray.line_intersection(l) for l in b.lines_for_shape]
        ts = [t for t in isects if t]
        if len(ts) > 1:
            t_vals.append(min(ts))
            indices.append(i)
    t_vals.sort()
    pts = [ray.point_at(t) for t in t_vals]
    result = []
    for i, index in enumerate(indices):
        result.append({
            'idx': buildings[index].idx,
            't': t_vals[i],
            'dist': t_vals[i] * geom.LAT_LON_TO_M,
            'address': buildings[index].address.full_address,
            'point': point_to_dict(pts[i])
        })
    return {
        'count': len(result),
        'result': result
    }
