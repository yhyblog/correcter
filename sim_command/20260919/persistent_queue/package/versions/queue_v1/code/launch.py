"""Old per-batch guard/restore entry is disabled in this new queue package."""
if __name__=='__main__':
    raise SystemExit('Use queue/main.py; nested per-batch lifecycle launch is prohibited')
