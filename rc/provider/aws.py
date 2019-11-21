from rc.util import run
import json
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_regions():
    regions = json.loads(run(
        ['aws', 'ec2', 'describe-regions', '--region', 'us-west-1']).stdout)['Regions']
    return list(map(lambda region: region['RegionName'], regions))
