"""Read-only CPU authorization/SHA validator. Never queries NVML or starts a wave."""
import argparse
import json
import sys
from core.release import load_authorization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--proposal', required=True)
    args = parser.parse_args()
    try:
        _, release, proposal = load_authorization(args.campaign, args.release, args.proposal)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'denied', 'error_type': type(error).__name__, 'error': str(error),
                          'CPU_only': True, 'NVML_queried': False, 'wave_started': False}))
        return 2
    print(json.dumps({'status': 'authorization_and_SHA_validated_CPU_only', 'release_id': release['release_id'],
                      'initialization_caps': proposal['initialization_caps'], 'NVML_queried': False,
                      'wave_started': False, 'runtime_environment_validated': False}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
