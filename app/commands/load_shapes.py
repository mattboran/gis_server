import json
import logging
from typing import Tuple, List
import os
import sys

import fiona

from api.db import db
from api.models import Building, Address
from commands.factory import Factory, BuildingShapeFactory, AddressedLocationFactory
from commands.util import Timer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def load_shapefile(filename: str, factory: Factory):
    if not os.path.isfile(filename):
        logger.error("Could not open %s", filename)
        return []
    with Timer(f"Reading {filename}"):
        with fiona.open(filename, 'r') as source:
            item_list = list(source)
    with Timer("Parsing items"):
        items = [factory.create(item, idx=idx) for idx, item in enumerate(item_list)]
        items = [item for item in items if item]
    return items

def generate_buildings_and_addresses(area: str) -> Tuple[List[Building], List[Address]]:
    building_factory = BuildingShapeFactory(region)
    address_factory = AddressedLocationFactory(region)
    buildings = load_shapefile(os.path.join(data_dir, f'{area}.shp'), building_factory)
    addresses = load_shapefile(os.path.join(data_dir, f'{area}_addresses.shp'), address_factory)
    buildings = get_unique_buildings([Building(**building) for building in buildings])
    addresses = [Address(**address) for address in addresses]
    return buildings, addresses

def get_unique_buildings(buildings: List[Building]) -> List[Building]:
    coord_set = set()
    result = []
    for building in buildings:
        key = json.dumps(building.polygon_points)
        if key not in coord_set:
            result.append(building)
            coord_set.add(key)
    return result

def create_buildings_and_addresses(buildings: List[Building], addresses: List[Address]):
    with Timer("Creating addresses"):
        with db.atomic():
            Address.bulk_create(addresses, batch_size=100)
    logger.info("Created %s addresses", len(address_models))
    with Timer("Creating buildings"):
        with db.atomic():
            Building.bulk_create(buildings, batch_size=100)
    logger.info("Created %s buildings", len(building_models))

if __name__ == "__main__":
    db.connect()
    models = [Address, Building]
    db.drop_tables(models)
    db.create_tables(models)
    n_grid = 200
    data_dir = os.path.join(os.getcwd(), 'gis_data')
    region = sys.argv[1]
    building_models, address_models = generate_buildings_and_addresses(region)
    create_buildings_and_addresses(building_models, address_models)
