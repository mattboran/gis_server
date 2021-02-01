from typing import List, Dict
import logging
import sys

from api.db import db
from api.models import Address, Street
from commands.util import Timer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def associate_streets(street_dict: Dict[str, Street], address_models: List[Address]) -> int:
    associated = 0
    for address in address_models:
        key_components = [address.predirective, address.street_name, address.post_type, address.postdirective]
        key = ' '.join([k for k in key_components if k])
        if not key:
            continue
        streets = street_dict.get(key.upper())
        if not streets:
            continue
        segments = [
            (s.idx, min(s.l_min_addr, s.r_min_addr), max(s.l_max_addr, s.r_max_addr))
            for s in streets
        ]
        known_segments = [s for s in segments if s[1] and s[2]]
        known_segments.sort(key=lambda x: (x[1], x[2]))
        for segment in known_segments:
            if segment[1] <= int(address.address_1) <= segment[2]:
                address.street_idx = segment[0]
                associated += 1
                break
    return associated

if __name__ == "__main__":
    region = sys.argv[1]
    with Timer("Creating street dict"):
        street_map = dict()
        street_query = Street.select().where(Street.region == region)
        for street in street_query:
            key = street.full_address_with_region
            if key in street_map:
                street_map[key].append(street)
            else:
                street_map[key] = [street]
    with Timer("Getting addresses"):
        addresses = list(Address.select().where(Address.region == region))
    with Timer("Associating streets"):
        result = associate_streets(street_map, addresses)
        logger.info("%s addresses associated.", result)
    with Timer("Updating address table"):
        with db.atomic():
            Address.bulk_update(addresses, fields=[Address.street_idx], batch_size=100)
