"""Only queue/qdrain.py owns the persistent inherited reservation."""
if __name__=='__main__':
    raise SystemExit('Use queue/qdrain.py; no independent batch reservation')
