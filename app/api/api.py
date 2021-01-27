import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import api.geometry as geom
from api.dependencies import get_token
from api.models import Bucket, Building, Address

from commands.util import Timer

router = APIRouter(dependencies=[Depends(get_token)])

logger = logging.getLogger(__name__)

class CoordinateOut(BaseModel):
    latitude: float
    longitude: float


class PointOut(BaseModel):
    x: float
    y: float


class AddressResult(BaseModel):
    address: str
    coord: CoordinateOut
    polygon_coords: Optional[List[CoordinateOut]]


class AddressOut(BaseModel):
    count: int
    result: List[AddressResult]


class IntersectionResult(BaseModel):
    idx: int
    t: float
    address: str
    point: CoordinateOut
    normal: PointOut
    face_length: float
    face_height: float


class IntersectionOut(BaseModel):
    count: int
    result: List[IntersectionResult]


def addresses_for_ids(idxs):
    return (Address.select(Address.idx, Address.predirective, Address.address_1, Address.street_name,
                           Address.post_type, Address.region)
                        .where(Address.idx << idxs))

def addresses_for_indices(indices):
    return (Address.select(Address.idx, Address.predirective, Address.address_1, Address.street_name,
                           Address.post_type, Address.region, Address.coord,
                           Address.building_idx, Address.street_idx, Building.idx,
                           Building.polygon_points, Building.height)
                        .where(Address.bucket_idx << indices)
                        .join(Building, attr='building', on=(Building.idx == Address.building_idx)))

def buildings_for_indices(indices):
    return (Building.select(Building.idx, Building.address_idxs, Building.polygon_points, Building.height)
                        .where(Building.bucket_idx << indices))

@router.get('/addresses', response_model=AddressOut)
async def get_addresses(region: str, lat: float, lon: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    addresses = addresses_for_indices(indices)
    result = []
    for address in addresses:
        coord = CoordinateOut(latitude=address.coord[0][1], longitude=address.coord[0][0])
        polygon = address.building.min_bounding_rect
        polygon_coords = [CoordinateOut(latitude=p[1], longitude=p[0]) for p in polygon]
        addr = AddressResult(address=address.full_name,
                             coord=coord,
                             polygon_coords=polygon_coords)
        result.append(addr)
    return {
        'count': len(result),
        'result': list(result)
    }

@router.get('/intersect', response_model=IntersectionOut)
async def get_intersection(region: str, lat: float, lon: float, heading: float):
    with Timer("Calculating intersection:"):
        indices = (Bucket.get(Bucket.region == region)
                        .indices_surrounding_coordinate((lon, lat)))
        buildings = buildings_for_indices(indices)
        t_vals, indices = [], []
        ray = geom.Ray((lon, lat), heading)
        for i, building in enumerate(buildings):
            isects = [ray.line_intersection(l) for l in building.lines_for_shape]
            ts = [t for t in isects if t]
            if len(ts) > 1:
                t_vals.append(min(ts, key=lambda t: t[0]))
                indices.append(i)
        pts = [t[1] for t in t_vals]
        normals = [t[2] for t in t_vals]
        face_lengths = [t[3] for t in t_vals]
        t_vals = [t[0] for t in t_vals]
        result = []
        for i, index in enumerate(indices):
            addr_idxs = buildings[index].address_idxs
            addresses = ",\n".join([address.full_name_without_region for address in addresses_for_ids(addr_idxs)])
            result.append(IntersectionResult(idx=buildings[index].idx,
                                             t=t_vals[i],
                                             address=addresses,
                                             point=CoordinateOut(latitude=pts[i][1], longitude=pts[i][0]),
                                             normal=PointOut(x=normals[i][0], y=normals[i][1]),
                                             face_length=face_lengths[i],
                                             face_height=buildings[index].height * geom.FT_TO_M or 5.0))
        result.sort(key=lambda r: r.t)
    return {
        'count': len(result),
        'result': result
    }
