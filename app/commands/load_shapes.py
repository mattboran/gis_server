import logging
from typing import Tuple, List
import os
import sys
from time import perf_counter

import fiona

from api.db import db
from api.models import Building, Address, Bucket
from api.geometry import Consolidator
from commands.factory import Factory, BuildingShapeFactory, AddressedLocationFactory

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def load_shapefile(filename: str, factory: Factory):
    start = perf_counter()
    with fiona.open(filename, 'r') as source:
        item_list = list(source)
        logger.info("Reading %s: %s s", filename, perf_counter() - start)
    start = perf_counter()
    items = [factory.create(item, idx=idx) for idx, item in enumerate(item_list)]
    items = [item for item in items if item]
    logger.info("Parsing %s entries: %s s.", len(items), perf_counter() - start)
    return items

def generate_buildings_and_addresses(area: str) -> Tuple[List[Building], List[Address]]:
    building_factory = BuildingShapeFactory(region)
    address_factory = AddressedLocationFactory(region)
    buildings = load_shapefile(os.path.join(data_dir, f'{area}.shp'), building_factory)
    addresses = load_shapefile(os.path.join(data_dir, f'{area}_addresses.shp'), address_factory)
    buildings = [Building(**building) for building in buildings]
    addresses = [Address(**address) for address in addresses]
    return buildings, addresses

def create_buildings_and_addresses(buildings: List[Building], addresses: List[Address]):
    start = perf_counter()
    with db.atomic():
        Address.bulk_create(addresses, batch_size=100)
    logger.info("Created %s addresses: %s s.", len(address_models), perf_counter() - start)
    start = perf_counter()
    with db.atomic():
        Building.bulk_create(buildings, batch_size=100)
    logger.info("Created %s buildings: %s s.", len(building_models), perf_counter() - start)

if __name__ == "__main__":
    db.connect()
    db.create_tables([Address, Building, Bucket])
    n_grid = 200
    data_dir = os.path.join(os.getcwd(), 'gis_data')
    region = sys.argv[1]
    building_models, address_models = generate_buildings_and_addresses(region)
    create_buildings_and_addresses(building_models, address_models)
    start_time = perf_counter()
    consolidator = Consolidator(building_models, address_models, n_grid=n_grid)
    consolidator.consolidate()
    logger.info("Consolidated in %s s.", perf_counter() - start_time)
    start_time = perf_counter()
    with db.atomic():
        Building.bulk_update(
            consolidator.buildings,
            fields=[Building.address_idx, Building.bucket_idx],
            batch_size=100
        )
    logger.info("Updated %s buildings in %s.", len(consolidator.buildings), perf_counter() - start_time)
    start_time = perf_counter()
    with db.atomic():
        Address.bulk_update(
            consolidator.addresses,
            fields=[Address.building_idx, Address.bucket_idx],
            batch_size=100
        )
    logger.info("Updated %s addresses in %s.", len(consolidator.addresses), perf_counter() - start_time)
    extent = consolidator.buildings_grid.extent
    coord_list = [(extent[0], extent[2]), (extent[1], extent[3])]
    Bucket.create(region=region, extent=coord_list,n_grid=n_grid)
    logger.info("Created '%s' which spans %s", region, coord_list)
