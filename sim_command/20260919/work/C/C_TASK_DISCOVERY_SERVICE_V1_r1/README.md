# C control service

The single active entry is `wakeup.py start` in this directory. It preserves the original C session and all shared C notification state. `task_discovery.py` adds CPU-only task_available detection; it never launches science. Read results/C/C_TASK_DISCOVERY_SERVICE_V1/REPORT.md and receipts/C/C_TASK_DISCOVERY_SERVICE_V1_RESULT.json for deployment, actual transport and handler-ACK proof.

Do not start a second notifier or clear delivery/outbox/ACK state. A machine or container restart requires host/boot/process reconciliation. A new scientific task must have a distinct authorized claim and must respect the existing formal-family exit barrier. Current scientific completion is recorded separately in nodes/C/COMPLETION.json; notification status never substitutes for a result.
