import sys

from rtree import index

from api.db import db
from api.models import Address, Building
from commands.util import Timer

def generate_buildings(region):
    for b in Building.all(region=region):
        if not b.bbox:
            continue
        minx, miny, maxx, maxy = b.bbox
        yield (b.idx, (minx, miny, maxx, maxy), b)

if __name__ == "__main__":
    region = sys.argv[1]
    with Timer("Generating index from buildings"):
        b_rtree = index.Index(f"buildings_{region}_rtree", generate_buildings(region))
    to_save = []
    with Timer("Associating address with building"):
        for a in Address.all(region=region):
            coord = tuple(a.center)
            nearest = list(b_rtree.nearest(coord, objects='raw'))[0]
            nearest.address_idxs.append(a.idx)
            to_save.append(nearest)
    with Timer("Saving buildings"):
        with db.atomic():
            Building.bulk_update(to_save, fields=[Building.address_idxs], batch_size=100)