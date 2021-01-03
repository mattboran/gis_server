from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import api.geometry as geom
from .dependencies import get_token
from .models import Bucket, Building

router = APIRouter(dependencies=[Depends(get_token)])

class CoordinateOut(BaseModel):
    latitude: float
    longitude: float


class PointOut(BaseModel):
    x: float
    y: float


class BucketOut(BaseModel):
    idx: int
    address: str
    height: Optional[float]
    ground_elevation: Optional[float]
    building_type: Optional[str]
    center: CoordinateOut
    origin: CoordinateOut
    polygon: List[PointOut]


class BucketResult(BaseModel):
    count: int
    result: List[BucketOut]


class IntersectionResult(BaseModel):
    idx: int
    t: float
    dist: float
    address: str
    point: CoordinateOut


class IntersectionOut(BaseModel):
    count: int
    result: List[IntersectionResult]


@router.get('/bucket', response_model=BucketResult)
async def get_bucket(region: str, lat: float, lon: float):
    bucket = Bucket.get(Bucket.region == region)
    indices = bucket.indices_surrounding_coordinate((lon, lat))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    result = []
    for b in buildings:
        c_lon, c_lat = b.address.coord[0]
        o_lon, o_lat = b.origin
        out = BucketOut(idx=b.idx,
                        address=b.address.full_address,
                        height=b.height * geom.FT_TO_M,
                        ground_elevation=b.ground_elevation * geom.FT_TO_M,
                        building_type=b.building_type,
                        center=CoordinateOut(latitude=c_lat, longitude=c_lon),
                        origin=CoordinateOut(latitude=o_lat, longitude=o_lon),
                        polygon=[PointOut(x=p[0], y=p[1]) for p in b.points_in_local_coords])
        result.append(out.dict())
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
        result.append(IntersectionResult(idx=buildings[index].idx,
                                         t=t_vals[i],
                                         dist=t_vals[i] * geom.LAT_LON_TO_M,
                                         address=buildings[index].address.full_address,
                                         point=CoordinateOut(latitude=pts[i][1], longitude=pts[i][0])).dict())
    return {
        'count': len(result),
        'result': result
    }
