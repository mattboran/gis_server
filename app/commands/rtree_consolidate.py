import logging
import sys

from rtree import index

from api.models import Address, Building
from commands.util import Timer

EPSILON = 0.000001

logger = logging.Logger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def generate_buildings(region):
    for b in Building.all(region):
        minx, miny, maxx, maxy = b.bbox
        yield (b.idx, (minx, miny, maxx, maxy), b)

def generate_addresses(region):
    for a in Address.all(region):
        minx, miny = a.center
        yield(a.idx, (minx, miny, minx + EPSILON, miny + EPSILON), a)

if __name__ == "__main__":
    region = sys.argv[1]
    with Timer("Generating index from buildings"):
        b_rtree = index.Index(f"buildings_{region}_rtree", generate_buildings(region))
    with Timer("Generating index from addresses"):
        a_rtree = index.Index(f"addresses_{region}_rtree", generate_addresses(region))
