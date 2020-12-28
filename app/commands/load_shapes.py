import logging
import os
import sys
from time import perf_counter

import fiona

from app.api.db import db
from app.api.models import Building, Address, Bucket
from app.api.geometry import Consolidator
from app.commands.factory import Factory, BuildingShapeFactory, AddressedLocationFactory

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def load_shapefile(filename: str, factory: Factory):
    start_time = perf_counter()
    with fiona.open(filename, 'r') as source:
        item_list = list(source)
        logger.info("Reading %s: %s s", filename, perf_counter() - start_time)
    start_time = perf_counter()
    items = [factory.create(item, idx=idx) for idx, item in enumerate(item_list)]
    items = [item for item in items if item]
    logger.info("Parsing %s buildings: %s s.", len(items), perf_counter() - start_time)
    return items

if __name__ == "__main__":
    db.connect()
    db.create_tables([Address, Building, Bucket])
    n_grid = 150
    data_dir = os.path.join(os.getcwd(), 'gis_data')
    region = sys.argv[1]
    building_factory = BuildingShapeFactory(region)
    address_factory = AddressedLocationFactory(region)
    buildings = load_shapefile(os.path.join(data_dir, f'{region}.shp'), building_factory)
    addresses = load_shapefile(os.path.join(data_dir, f'{region}_addresses.shp'), address_factory)
    building_models = [Building(**building) for building in buildings]
    address_models = [Address(**address) for address in addresses]
    with db.atomic():
        Address.bulk_create(address_models, batch_size=100)
    with db.atomic():
        Building.bulk_create(building_models, batch_size=100)
    consolidator = Consolidator(building_models, address_models, n_grid=n_grid)
    consolidator.consolidate()
    with db.atomic():
        Building.bulk_update(
            consolidator.buildings,
            fields=[Building.address_idx, Building.bucket_id],
            batch_size=100
        )
    extent = consolidator.buildings_grid.extent
    coord_list = [(extent[0], extent[2]), (extent[1], extent[3])]
    Bucket.create(region=region, extent=coord_list,n_grid=n_grid)
