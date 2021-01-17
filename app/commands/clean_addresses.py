
from collections import Counter
import logging
from typing import Dict, List
import sys

from api.db import db
from api.models import Building, Address
from commands.util import Timer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def all_addresses(city):
    return (Address.select(Address.idx, Address.predirective, Address.address_1, Address.street_name,
                           Address.post_type, Address.region, Address.coord,
                           Address.building_idx, Address.street_idx, Building.idx,
                           Building.polygon_points)
                        .where(Address.region == city)
                        .join(Building, attr='building', on=(Building.idx == Address.building_idx)))

def address_dict(addresses):
    result: Dict[str, List[Address]] = dict()
    for address in addresses:
        components = [address.predirective, address.address_1, address.street_name, address.post_type, address.region]
        full_address = " ".join([c for c in components if c])
        if full_address in result:
            result[full_address].append(address)
        else:
            result[full_address] = [address]
    return result

def uniquify(address_result):
    saved_count, deleted_count, skip_count = 0, 0, 0
    for models in address_result.values():
        if len(models) == 1:
            skip_count += 1
            continue
        coords = [addr.coord[0] for addr in models]
        # The most common polygon is most likely the correct one:
        try:
            building_counter = Counter([a.building_idx for a in models])
            building_idx = building_counter.most_common(1).pop()[0]
        except IndexError:
            building_idx = None
        longitude: float = sum([c[0] for c in coords]) / float(len(coords))
        latitude: float = sum([c[1] for c in coords]) / float(len(coords))
        unique_result = models[0]
        unique_result.coord = [[longitude, latitude]]
        unique_result.building_idx = building_idx
        other_results = models[1:]
        saved_count += 1
        deleted_count += len(other_results)
        with db.atomic():
            unique_result.save()
            for a in other_results:
                a.delete_instance()
    logger.info("Addresses: Updated %s, deleted %s, skipped %s", saved_count, deleted_count, skip_count)

if __name__ == "__main__":
    region = sys.argv[1]
    with Timer("Fetching all addresses"):
        address_models = list(all_addresses(region))
    with Timer("Creating address dict"):
        address_map = address_dict(address_models)
    with Timer("Uniquifiyng"):
        uniquify(address_map)
