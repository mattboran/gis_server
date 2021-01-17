import json
import logging
from collections import Counter
from typing import List, Optional, Dict, Any

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

    @property
    def hashable_polygon_coords(self) -> Optional[str]:
        if not self.polygon_coords:
            return None
        polygons = [json.dumps(p.dict()) for p in self.polygon_coords]
        return "[" + ",".join(polygons) + "]"


class AddressOut(BaseModel):
    count: int
    result: List[Any]


class IntersectionResult(BaseModel):
    idx: int
    t: float
    dist: float
    address: str
    point: CoordinateOut


class IntersectionOut(BaseModel):
    count: int
    result: List[IntersectionResult]


def addresses_for_indices(indices):
    return (Address.select(Address.predirective, Address.address_1, Address.street_name,
                           Address.post_type, Address.region, Address.coord,
                           Address.building_idx, Address.street_idx, Building.idx,
                           Building.polygon_points)
                        .where(Address.bucket_idx << indices)
                        .join(Building, attr='building', on=(Building.idx == Address.building_idx)))

def address_output(addresses):
    result = []
    for address in addresses:
        predirective = f" {address.predirective} " if address.predirective else ""
        street = address.address_1 + predirective + address.street_name + " " + address.post_type
        full_address = street + ", " + address.region
        coord = CoordinateOut(latitude=address.coord[0][1], longitude=address.coord[0][0])
        polygon = address.building.min_bounding_rect
        polygon_coords = [CoordinateOut(latitude=p[1], longitude=p[0]) for p in polygon]
        addr = AddressResult(address=full_address,
                            coord=coord,
                            polygon_coords=polygon_coords)
        result.append(addr)
    return result

@router.get('/addresses', response_model=AddressOut)
async def get_addresses(region: str, lat: float, lon: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    addresses = addresses_for_indices(indices)
    result = address_output(addresses)
    return {
        'count': len(result),
        'result': list(result)
    }

@router.get('/intersect', response_model=IntersectionOut)
async def get_intersection(region: str, lat: float, lon: float, heading: float):
    with Timer("Calculating intersection:"):
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
