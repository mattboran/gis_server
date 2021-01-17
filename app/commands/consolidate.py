import logging
import sys

from api.db import db
from api.models import Building, Address, Bucket
from api.geometry import Consolidator
from commands.util import Timer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

if __name__ == "__main__":
    region = sys.argv[1]
    try:
        n_grid = sys.argv[2]
    except IndexError:
        n_grid = 200
    with Timer("Reading buildings and addresses from DB"):
        building_models = list(Building.select().where(Building.region == region))
        address_models = list(Address.select().where(Address.region == region))
    with Timer("Consolidating buildings and addresses"):
        consolidator = Consolidator(building_models, address_models, n_grid=n_grid)
        consolidator.consolidate()
    with Timer("Updating Buildings in db"):
        with db.atomic():
            Building.bulk_update(
                consolidator.buildings,
                fields=[Building.address_idx, Building.bucket_idx],
                batch_size=100
            )
    with Timer("Updating addresses in db"):
        with db.atomic():
            Address.bulk_update(
                consolidator.addresses,
                fields=[Address.building_idx, Address.bucket_idx],
                batch_size=100
            )
    extent = consolidator.buildings_grid.extent
    coord_list = [(extent[0], extent[2]), (extent[1], extent[3])]
    Bucket.create(region=region, extent=coord_list,n_grid=n_grid)
    logger.info("Created '%s' which spans %s", region, coord_list)
