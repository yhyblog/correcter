"""CPU-only guard usable by an existing native task before any evaluation load."""
import json,sys
from pathlib import Path
import paths
from paths import ORIGINAL,CAMPAIGN
from qio import read,sha
from selection import validate_selection,POST_RULE_SHA

def main():
    override=CAMPAIGN/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'
    if sha(override)!=POST_RULE_SHA or read(override)['status']!='released':raise ValueError('Post-only override changed')
    row=read(ORIGINAL/'SELECTION.json');lock=read(ORIGINAL/'SELECTION_LOCK.json')
    if not lock['immutable'] or sha(ORIGINAL/'SELECTION.json')!=lock['selection']['sha256']:raise ValueError('A immutable selection changed')
    chosen=validate_selection(row)
    if len(sys.argv)>1 and chosen!=sys.argv[1]:raise ValueError('native consumed choice differs from Post-only winner')
    print(json.dumps(dict(status='valid_Post_only',chosen_loss=chosen,fixed_fit_seed=9101,override_sha256=POST_RULE_SHA)))

if __name__=='__main__':main()
