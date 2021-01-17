from typing import Any, Dict, Optional

class Factory: # pylint: disable=too-few-public-methods    

    def __init__(self, region: str):
        self.region = region

    def create(self, data:dict, idx: int) -> Dict[str, Any]:
        return getattr(self, f'create_{self.region}')(data, idx)


class BuildingShapeFactory(Factory):

    def create_denver(self, data: dict, idx: int) -> Optional[Dict[str, Any]]:
        properties = data['properties']
        building_type = properties['BLDG_TYPE']
        if building_type == 'Garage/Shed':
            return None
        return {
            'idx': idx,
            'region': self.region,
            'building_id': properties['BUILDING_I'],
            'height': properties['BLDG_HEIGH'],
            'ground_elevation': properties['GROUND_ELE'],
            'building_type': building_type,
            'polygon_points': data['geometry']['coordinates'][0]
        }


class AddressedLocationFactory(Factory):

    def create_denver(self, data: dict, idx: int) -> Optional[Dict[str, Any]]:
        properties = data['properties']
        building_type = properties['BUILDING_T']
        if building_type == 'Garage/Shed':
            return None
        coord = [(properties['LONGITUDE'], properties['LATITUDE'])]
        return {
            'idx': idx,
            'region': self.region,
            'building_type': building_type,
            'address_1': int(properties['ADDRESS__1']),
            'address_2': properties['ADDRESS__2'],
            'predirective': properties['PREDIRECTI'],
            'postdirective': properties['POSTDIRECT'],
            'street_name': properties['STREET_NAM'],
            'post_type': properties['POSTTYPE'],
            'full_address': properties['FULL_ADDRE'],
            'coord': coord
        }


class StreetFactory(Factory):

    def create_denver(self, data: dict, idx: int) -> Optional[Dict[str, Any]]:
        properties = data['properties']
        coords = data['geometry']['coordinates']
        fullname = properties['FULLNAME']
        if not coords or not fullname:
            return None
        return {
            'idx': idx,
            'region': self.region,
            'l_min_addr': properties['L_F_ADD'],
            'l_max_addr': properties['L_T_ADD'],
            'r_min_addr': properties['R_F_ADD'],
            'r_max_addr': properties['R_T_ADD'],
            'prefix': properties['PREFIX'],
            'name': properties['NAME'],
            'street_type': properties['TYPE'],
            'suffix': properties['SUFFIX'],
            'full_name': fullname,
            'coords': coords
        }
