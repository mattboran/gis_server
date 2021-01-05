import logging
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import api.geometry as geom
from .dependencies import get_token
from .models import Bucket, Building, Address

router = APIRouter(dependencies=[Depends(get_token)])

logger = logging.getLogger(__name__)

class CoordinateOut(BaseModel):
    latitude: float
    longitude: float


class PointOut(BaseModel):
    x: float
    y: float


class BucketResult(BaseModel):
    idx: int
    address: str
    height: Optional[float]
    ground_elevation: Optional[float]
    building_type: Optional[str]
    center: CoordinateOut
    origin: CoordinateOut
    polygon: List[PointOut]
    polygon_coords: List[CoordinateOut]


class BucketOut(BaseModel):
    count: int
    result: List[BucketResult]


class AddressResult(BaseModel):
    address: str
    building_idx: Optional[int]
    coord: CoordinateOut


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


@router.get('/bucket', response_model=BucketOut)
async def get_bucket(region: str, lat: float, lon: float):
    bucket = Bucket.get(Bucket.region == region)
    indices = bucket.indices_surrounding_coordinate((lon, lat))
    buildings = Building.get_buildings_for_bucket_indices(indices)
    result = []
    for b in buildings:
        c_lon, c_lat = b.address.coord[0]
        o_lon, o_lat = b.origin
        poly_coords = [CoordinateOut(latitude=p[1], longitude=p[0]) for p in b.polygon_points]
        out = BucketResult(idx=b.idx,
                           address=b.address.full_address,
                           height=b.height * geom.FT_TO_M,
                           ground_elevation=b.ground_elevation * geom.FT_TO_M,
                           building_type=b.building_type,
                           center=CoordinateOut(latitude=c_lat, longitude=c_lon),
                           origin=CoordinateOut(latitude=o_lat, longitude=o_lon),
                           polygon=[PointOut(x=p[0], y=p[1]) for p in b.points_in_local_coords],
                           polygon_coords=poly_coords)
        result.append(out.dict())
    return {
        'count': len(result),
        'result': result
    }

@router.get('/addresses', response_model=AddressOut)
async def get_addresses(region: str, lat: float, lon: float):
    indices = (Bucket.get(Bucket.region == region)
                     .indices_surrounding_coordinate((lon, lat)))
    addresses = (Address.select(Address.building_type, Address.address_1,
                                Address.street_name, Address.coord,
                                Address.post_type, Address.predirective,
                                Address.region, Address.building_idx)
                        .where(Address.bucket_idx << indices))
    result = dict()
    for address in addresses:
        predirective = f" {address.predirective} " if address.predirective else ""
        street = address.address_1 + predirective + address.street_name + " " + address.post_type
        full_address = street + ", " + address.region
        coord = CoordinateOut(latitude=address.coord[0][1], longitude=address.coord[0][0])
        addr = AddressResult(address=full_address, coord=coord, building_idx=address.building_idx)
        if result.get(full_address):
            result[full_address].append(addr)
        else:
            result[full_address] = [addr]
    
    # Group multiple addresses that share the same street together and average their center point
    for key, value in result.items():
        coords = [val.coord for val in value]
        # The most common building_idx is most likely the correct one:
        try:
            building_idx = Counter([v.building_idx for v in value]).most_common(1).pop()[0]
        except IndexError:
            building_idx = None
        latitude = sum([c.latitude for c in coords]) / float(len(coords))
        longitude = sum([c.longitude for c in coords]) / float(len(coords))
        coord = CoordinateOut(latitude=latitude, longitude=longitude)
        result[key] = AddressResult(address=key, coord=coord, building_idx=building_idx).dict()
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
