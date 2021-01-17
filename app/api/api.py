import json
import logging
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from shapely.geometry import Point

import api.geometry as geom
from .dependencies import get_token
from .models import Bucket, Building, Address, Street

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
    street_coords: Optional[List[CoordinateOut]]

    @property
    def hashable_polygon_coords(self) -> Optional[str]:
        if not self.polygon_coords:
            return None
        polygons = [json.dumps(p.dict()) for p in self.polygon_coords]
        return "[" + ",".join(polygons) + "]"


class AddressOut(BaseModel):
    count: int
    result: List[AddressResult]


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
                           Building.polygon_points, Street.idx, Street.coords)
                        .where(Address.bucket_idx << indices)
                        .join(Building, attr='building', on=(Building.idx == Address.building_idx))
                        .switch(Address)
                        .join(Street, attr='street', on=(Street.idx == Address.street_idx)))

def address_dict(addresses):
    result = dict()
    for address in addresses:
        predirective = f" {address.predirective} " if address.predirective else ""
        street = address.address_1 + predirective + address.street_name + " " + address.post_type
        full_address = street + ", " + address.region
        coord = CoordinateOut(latitude=address.coord[0][1], longitude=address.coord[0][0])
        polygon_coords = [CoordinateOut(latitude=p[1], longitude=p[0]) for p in address.building.polygon_points]
        street_coords = [CoordinateOut(latitude=p[1], longitude=p[0]) for p in address.street.coords if address.street]
        addr = AddressResult(address=full_address,
                            coord=coord,
                            polygon_coords=polygon_coords,
                            street_coords=street_coords)
        if full_address in result:
            result[full_address].append(addr)
        else:
            result[full_address] = [addr]
    return result

def unique_address_dict(address_dict):
    for full_address, address_models in address_dict.items():
        coords = [addr.coord for addr in address_models]
        # The most common polygon is most likely the correct one:
        try:
            polygons = [addr.hashable_polygon_coords for idx, addr in enumerate(address_models)]
            polygon = json.loads(Counter(polygons).most_common(1).pop()[0])
        except IndexError:
            polygon = None
        latitude = sum([c.latitude for c in coords]) / float(len(coords))
        longitude = sum([c.longitude for c in coords]) / float(len(coords))
        coord = CoordinateOut(latitude=latitude, longitude=longitude)
        street_coords = address_models[0].street_coords
        address_dict[full_address] = AddressResult(address=full_address, 
                                                   coord=coord,
                                                   polygon_coords=polygon,
                                                   street_coords=street_coords)
    return address_dict

@router.get('/addresses', response_model=AddressOut)
async def get_addresses(region: str, lat: float, lon: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    addresses = addresses_for_indices(indices)
    result = address_dict(addresses)
    result = unique_address_dict(result)
    return {
        'count': len(result),
        'result': list(result.values())
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
