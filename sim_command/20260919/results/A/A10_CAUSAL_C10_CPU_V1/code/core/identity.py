import re
import subprocess

class ContractError(ValueError): pass
Refused = ContractError

def check_policy_uuid(raw, expected, cuuuid_type, *, before_conversion=None):
    """Return evidence; the caller persists it before enforcing the decision.

    cuuuid_type is the class token from the already imported torch._C._CUuuid.
    CPU tests inject a controlled class; names and arbitrary __str__ methods
    never grant support. No device query, byte decoding or endian inference.
    """
    raw_type = type(raw)
    trusted_class_available = isinstance(cuuuid_type, type)
    if raw_type is str:
        branch = 'native_str'
    elif trusted_class_available and raw_type is cuuuid_type:
        branch = 'torch_C_CUuuid_identity'
    else:
        branch = 'unsupported'
    evidence = dict(
        raw_type_module=raw_type.__module__, raw_type_qualname=raw_type.__qualname__,
        supported_type_branch=branch, trusted_class_available=trusted_class_available,
        trusted_class_module=cuuuid_type.__module__ if trusted_class_available else None,
        trusted_class_qualname=cuuuid_type.__qualname__ if trusted_class_available else None,
        trusted_class_identity_match=trusted_class_available and raw_type is cuuuid_type,
        torch_uuid_text=None, expected_uuid=expected, normalized_uuid=None,
        conversion_calls=0, conversion_status='not_entered', conversion_error=None,
        format_valid=None, expected_format_valid=None, target_matches=None,
        accepted=False, reason='not_evaluated')
    if before_conversion is not None:
        before_conversion(dict(evidence))
    if branch == 'unsupported':
        evidence.update(conversion_status='rejected_without_conversion', reason='unsupported_uuid_type')
        return evidence
    if branch == 'native_str':
        evidence.update(torch_uuid_text=raw, conversion_status='not_needed_native_str')
    else:
        evidence['conversion_calls'] = 1
        try:
            evidence['torch_uuid_text'] = str(raw)  # exactly once, only trusted type
        except Exception as error:
            evidence.update(conversion_status='raised', reason='uuid_conversion_failed',
                conversion_error=dict(module=type(error).__module__,
                    qualname=type(error).__qualname__, message=str(error)))
            return evidence
        evidence['conversion_status'] = 'returned'
    pattern = r'(?:GPU-)?[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
    text = evidence['torch_uuid_text']
    evidence['format_valid'] = type(text) is str and re.fullmatch(pattern, text, re.ASCII) is not None
    evidence['expected_format_valid'] = type(expected) is str and re.fullmatch(pattern, expected, re.ASCII) is not None
    if not evidence['format_valid'] or not evidence['expected_format_valid']:
        evidence['reason'] = 'malformed_uuid_text' if not evidence['format_valid'] else 'malformed_expected_uuid'
        return evidence
    actual = 'GPU-' + text.removeprefix('GPU-').lower()
    target = 'GPU-' + expected.removeprefix('GPU-').lower()
    evidence.update(normalized_uuid=actual, target_matches=actual == target,
                    accepted=actual == target, reason='accepted' if actual == target else 'uuid_mismatch')
    return evidence
def normalize_pci(value):
    m = re.fullmatch(r'([0-9a-fA-F]{4}|[0-9a-fA-F]{8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', value)
    if not m:
        raise Refused('Malformed PCI identity')
    domain, bus, device, function = [int(v, 16) for v in m.groups()]
    if domain > 0xffff or device > 0x1f:
        raise Refused('PCI value outside frozen host domain/device range')
    return f'{domain:04x}:{bus:02x}:{device:02x}.{function:x}'
def verify_device(release, proposal, query=None):
    """One future NVML CLI query per caller; never called by CPU checker."""
    output = query if query is not None else subprocess.run(
        ['nvidia-smi', '--query-gpu=index,uuid,name,driver_version,pci.bus_id', '--format=csv,noheader'],
        check=True, capture_output=True, text=True, timeout=15).stdout
    rows = [[x.strip() for x in line.split(',')] for line in output.splitlines()]
    if len(rows) != 8 or any(len(r) != 5 for r in rows):
        raise ContractError('Exactly eight NVML identities required')
    inventory = {r['gpu_uuid']: r['pci_bus_id'] for r in proposal['physical_inventory']}
    actual = {}
    for index, uid, name, driver, pci in rows:
        if uid in actual or driver != release['driver'] or name != release['gpu_model']:
            raise ContractError('NVML UUID/model/driver conflict')
        actual[uid] = normalize_pci(pci)
        if uid == release['gpu_uuid'] and index != str(release['gpu_index']):
            raise ContractError('Fixed physical NVML index changed')
    if actual != inventory or actual.get(release['gpu_uuid']) != release['pci_bus_id']:
        raise ContractError('NVML physical inventory differs from frozen mapping inputs')
    return rows
