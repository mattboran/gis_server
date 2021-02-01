
import logging
from typing import Dict, List
import sys

from api.db import db
from api.models import Address
from commands.util import Timer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def address_dict(area) -> Dict[str, List[Address]]:
    result: Dict[str, List[Address]] = dict()
    for address in Address.all(area):
        full_address = address.full_address_with_region
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
        longitude: float = sum([c[0] for c in coords]) / float(len(coords))
        latitude: float = sum([c[1] for c in coords]) / float(len(coords))
        unique_result = models[0]
        unique_result.coord = [[longitude, latitude]]
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
    with Timer("Creating address dict"):
        address_map = address_dict(region)
    with Timer("Uniquifiyng"):
        uniquify(address_map)
