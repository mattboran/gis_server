import logging
import os
import sys
from time import perf_counter

import fiona

from models import Building, Address
from commands.factory import Factory, BuildingShapeFactory, AddressedLocationFactory # pylint: disable=import-error

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
    data_dir = os.path.join(os.getcwd(), 'gis_data')
    region = sys.argv[1]
    building_factory = BuildingShapeFactory(region)
    address_factory = AddressedLocationFactory(region)
    buildings = load_shapefile(os.path.join(data_dir, f'{region}.shp'), building_factory)
    addresses = load_shapefile(os.path.join(data_dir, f'{region}_addresses.shp'), address_factory)
    building_models = [Building(**building) for building in buildings]
    address_models = [Address(**address) for address in addresses]
    import pdb; pdb.set_trace()