#!/usr/bin/env bash
# Safely hand all visible GPUs from the keep-alive workload to a formal job and
# restore the keep-alive workload after every normal/error/signal exit path.

set -uo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOLDER_SCRIPT="${GPU_HOLDER_SCRIPT:-${WORKSPACE_ROOT}/gpu_hold.py}"
HOLDER_PYTHON="${GPU_HOLDER_PYTHON:-/usr/bin/python}"
HOLDER_DEVICES="${GPU_HOLDER_DEVICES:-0,1,2,3,4,5,6,7}"
HOLDER_SIZE="${GPU_HOLDER_SIZE:-8192}"
HOLDER_DTYPE="${GPU_HOLDER_DTYPE:-bf16}"
HOLDER_LOG_INTERVAL="${GPU_HOLDER_LOG_INTERVAL:-30}"
HOLDER_TARGET_UTIL="${GPU_HOLDER_TARGET_UTIL:-0.50}"
HOLDER_PERIOD_SECONDS="${GPU_HOLDER_PERIOD_SECONDS:-0.20}"
EXPECTED_GPUS="${GPU_HOLDER_EXPECTED_GPUS:-8}"
MIN_MEMORY_MIB="${GPU_HOLDER_MIN_MEMORY_MIB:-900}"
MIN_UTILIZATION="${GPU_HOLDER_MIN_UTILIZATION:-50}"
VERIFY_TIMEOUT_SECONDS="${GPU_HOLDER_VERIFY_TIMEOUT_SECONDS:-120}"
STOP_TIMEOUT_SECONDS="${GPU_HOLDER_STOP_TIMEOUT_SECONDS:-60}"
RETRY_SECONDS="${GPU_HOLDER_RETRY_SECONDS:-10}"

PID_FILE="${GPU_HOLDER_PID_FILE:-${WORKSPACE_ROOT}/gpu_hold_managed.pid}"
HOLDER_LOG="${GPU_HOLDER_LOG_FILE:-${WORKSPACE_ROOT}/gpu_hold_managed.log}"
LIFECYCLE_LOG="${GPU_HOLDER_LIFECYCLE_LOG:-${WORKSPACE_ROOT}/gpu_occupancy_lifecycle.log}"

timestamp() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

log() {
    printf '[%s] %s\n' "$(timestamp)" "$*" | tee -a "${LIFECYCLE_LOG}" >&2
}

is_holder_manager() {
    local pid="$1"
    local -a argv=()
    local executable

    [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
    [[ -r "/proc/${pid}/cmdline" ]] || return 1
    mapfile -d '' -t argv < "/proc/${pid}/cmdline" || return 1
    (( ${#argv[@]} >= 2 )) || return 1
    executable="$(basename "${argv[0]}")"
    [[ "${executable}" == python || "${executable}" == python3 ]] || return 1
    [[ "${argv[1]}" == "${HOLDER_SCRIPT}" ]] || return 1
    return 0
}

find_holder_managers() {
    local candidate
    local -a candidates=()

    if [[ -r "${PID_FILE}" ]]; then
        candidate="$(sed -n '1p' "${PID_FILE}" 2>/dev/null || true)"
        [[ "${candidate}" =~ ^[0-9]+$ ]] && candidates+=("${candidate}")
    fi
    while IFS= read -r candidate; do
        [[ -n "${candidate}" ]] && candidates+=("${candidate}")
    done < <(pgrep -f "${HOLDER_SCRIPT}" 2>/dev/null || true)

    for candidate in "${candidates[@]}"; do
        if is_holder_manager "${candidate}"; then
            printf '%s\n' "${candidate}"
        fi
    done | sort -n -u
}

gpu_rows_meet_threshold() {
    local rows=0
    local ok=1
    local index memory utilization

    while IFS=',' read -r index memory utilization; do
        index="${index//[[:space:]]/}"
        memory="${memory//[[:space:]]/}"
        utilization="${utilization//[[:space:]]/}"
        [[ -n "${index}" ]] || continue
        rows=$((rows + 1))
        if ! [[ "${memory}" =~ ^[0-9]+$ && "${utilization}" =~ ^[0-9]+$ ]]; then
            ok=0
        elif (( memory < MIN_MEMORY_MIB || utilization < MIN_UTILIZATION )); then
            ok=0
        fi
    done < <(
        nvidia-smi \
            --query-gpu=index,memory.used,utilization.gpu \
            --format=csv,noheader,nounits 2>/dev/null || true
    )

    (( rows == EXPECTED_GPUS && ok == 1 ))
}

verify_started_once() {
    local -a managers=()
    mapfile -t managers < <(find_holder_managers)
    (( ${#managers[@]} == 1 )) || return 1
    kill -0 "${managers[0]}" 2>/dev/null || return 1
    gpu_rows_meet_threshold
}

verify_started() {
    local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
    local consecutive=0

    while (( SECONDS < deadline )); do
        if verify_started_once; then
            consecutive=$((consecutive + 1))
            if (( consecutive >= 2 )); then
                return 0
            fi
        else
            consecutive=0
        fi
        sleep 2
    done
    return 1
}

gpu_compute_process_count() {
    local output

    # Fail closed when NVML/device access is unavailable.  Treating a failed
    # nvidia-smi as an empty process list could launch a formal job without
    # proving that the GPUs were actually released.
    if ! output="$(nvidia-smi \
        --query-compute-apps=pid \
        --format=csv,noheader,nounits 2>/dev/null)"; then
        return 1
    fi
    awk 'NF { count += 1 } END { print count + 0 }' <<< "${output}"
}

process_group_id() {
    local pid="$1"
    local stat_line remainder state parent pgid

    [[ -r "/proc/${pid}/stat" ]] || return 1
    IFS= read -r stat_line < "/proc/${pid}/stat" || return 1
    # /proc/PID/stat field 2 is parenthesized and may contain spaces.  Remove
    # it first; the remaining first three fields are state, ppid and pgrp.
    remainder="${stat_line##*) }"
    read -r state parent pgid _ <<< "${remainder}"
    [[ "${pgid:-}" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "${pgid}"
}

stop_holder() {
    local -a managers=()
    local pid pgid deadline compute_count

    mapfile -t managers < <(find_holder_managers)
    if (( ${#managers[@]} == 0 )); then
        log 'GPU occupancy program is already stopped.'
    else
        for pid in "${managers[@]}"; do
            pgid="$(process_group_id "${pid}" 2>/dev/null || true)"
            log "Stopping GPU occupancy manager pid=${pid} pgid=${pgid:-unknown}."
            if [[ "${pgid}" =~ ^[0-9]+$ && "${pgid}" == "${pid}" ]]; then
                kill -TERM -- "-${pgid}" 2>/dev/null || true
            else
                kill -TERM "${pid}" 2>/dev/null || true
            fi
        done
    fi

    deadline=$((SECONDS + STOP_TIMEOUT_SECONDS))
    while (( SECONDS < deadline )); do
        mapfile -t managers < <(find_holder_managers)
        compute_count="$(gpu_compute_process_count 2>/dev/null || printf 'unknown')"
        if (( ${#managers[@]} == 0 )) && [[ "${compute_count}" == 0 ]]; then
            : > "${PID_FILE}"
            log 'GPU occupancy program stopped; all GPU compute contexts are clear.'
            return 0
        fi
        sleep 1
    done

    mapfile -t managers < <(find_holder_managers)
    for pid in "${managers[@]}"; do
        pgid="$(process_group_id "${pid}" 2>/dev/null || true)"
        log "Graceful stop timed out; force-stopping confirmed holder pid=${pid} pgid=${pgid:-unknown}."
        if [[ "${pgid}" =~ ^[0-9]+$ && "${pgid}" == "${pid}" ]]; then
            kill -KILL -- "-${pgid}" 2>/dev/null || true
        else
            kill -KILL "${pid}" 2>/dev/null || true
        fi
    done
    sleep 2

    mapfile -t managers < <(find_holder_managers)
    compute_count="$(gpu_compute_process_count 2>/dev/null || printf 'unknown')"
    if (( ${#managers[@]} > 0 )) || [[ "${compute_count}" != 0 ]]; then
        log 'ERROR: GPU occupancy program or another GPU compute process is still present.'
        return 1
    fi
    : > "${PID_FILE}"
    log 'GPU occupancy program force-stopped; all GPU compute contexts are clear.'
}

start_holder_once() {
    local -a managers=()

    mapfile -t managers < <(find_holder_managers)
    if (( ${#managers[@]} == 1 )); then
        log "GPU occupancy manager already exists at pid=${managers[0]}; verifying it."
    elif (( ${#managers[@]} > 1 )); then
        log 'Multiple GPU occupancy managers found; cleaning them before restart.'
        stop_holder || return 1
    else
        : > "${PID_FILE}"
        log "Starting GPU occupancy program after formal command: devices=${HOLDER_DEVICES}."
        "${HOLDER_PYTHON}" "${HOLDER_SCRIPT}" \
            --devices "${HOLDER_DEVICES}" \
            --size "${HOLDER_SIZE}" \
            --dtype "${HOLDER_DTYPE}" \
            --log-interval "${HOLDER_LOG_INTERVAL}" \
            --target-util "${HOLDER_TARGET_UTIL}" \
            --period-seconds "${HOLDER_PERIOD_SECONDS}" \
            --daemon \
            --pid-file "${PID_FILE}" \
            --log-file "${HOLDER_LOG}" \
            >> "${LIFECYCLE_LOG}" 2>&1 || return 1
    fi

    if verify_started; then
        mapfile -t managers < <(find_holder_managers)
        log "GPU occupancy program verified on ${EXPECTED_GPUS} GPUs; manager pid=${managers[0]}."
        return 0
    fi
    log 'GPU occupancy startup verification failed.'
    stop_holder || true
    return 1
}

ensure_started() {
    local attempt=1
    while true; do
        log "GPU occupancy restore attempt ${attempt}."
        if start_holder_once; then
            return 0
        fi
        log "GPU occupancy restore attempt ${attempt} failed; retrying in ${RETRY_SECONDS}s."
        attempt=$((attempt + 1))
        sleep "${RETRY_SECONDS}"
    done
}

show_status() {
    local -a managers=()
    mapfile -t managers < <(find_holder_managers)
    printf 'holder_managers=%s\n' "${managers[*]:-none}"
    nvidia-smi \
        --query-gpu=index,memory.used,utilization.gpu,power.draw \
        --format=csv,noheader
    if verify_started_once; then
        printf 'status=verified\n'
    else
        printf 'status=not-verified\n'
        return 1
    fi
}

run_formal_command() {
    # Reserve before the guard releases CUDA contexts, including model-loading time.
    if /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" active; then
        /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" run -- "$@"
        return $?
    fi
    local training_pid=''
    local training_status=0
    local restore_complete=0

    if (( $# == 0 )); then
        printf 'run requires a formal training command after --\n' >&2
        return 2
    fi

    restore_on_exit() {
        local original_status=$?
        trap - EXIT
        trap '' INT TERM HUP
        if (( ${restore_complete:-0} == 0 )); then
            log "Formal command exited with status ${original_status}; restoring occupancy from EXIT trap."
            ensure_started
        fi
        exit "${original_status}"
    }

    forward_signal() {
        local signal_name="$1"
        log "Received ${signal_name}; forwarding it to formal command process group."
        if [[ "${training_pid}" =~ ^[0-9]+$ ]] && kill -0 "${training_pid}" 2>/dev/null; then
            kill "-${signal_name}" -- "-${training_pid}" 2>/dev/null \
                || kill "-${signal_name}" "${training_pid}" 2>/dev/null \
                || true
        fi
    }

    # Install the recovery path before releasing the GPUs. Any ordinary shell
    # error, Ctrl-C, TERM, or HUP after this point restores and verifies holder.
    trap restore_on_exit EXIT
    trap 'forward_signal INT' INT
    trap 'forward_signal TERM' TERM
    trap 'forward_signal HUP' HUP

    if ! stop_holder; then
        training_status=1
        log 'Formal command was not launched because GPU release could not be verified; restoring occupancy.'
        ensure_started
        restore_complete=1
        trap - EXIT INT TERM HUP
        return "${training_status}"
    fi
    log "Launching formal command: $*"

    # setsid gives torchrun and all descendants a dedicated process group so a
    # termination signal can be forwarded to the complete training job.
    setsid --wait "$@" &
    training_pid=$!
    # A trapped signal interrupts bash's wait before the child has exited.
    # Keep waiting for the command's cleanup, so the holder cannot overlap it.
    while true; do
        wait "${training_pid}"
        training_status=$?
        if ! kill -0 "${training_pid}" 2>/dev/null; then
            break
        fi
    done
    training_pid=''

    # This command is intentionally after the formal command. It retries until
    # both the process and all eight GPU thresholds have been verified twice.
    ensure_started
    restore_complete=1
    trap - EXIT INT TERM HUP
    log "Formal command status=${training_status}; verified occupancy restoration complete."
    return "${training_status}"
}

usage() {
    cat <<'EOF'
Usage:
  gpu_occupancy_lifecycle.sh stop
  gpu_occupancy_lifecycle.sh start
  gpu_occupancy_lifecycle.sh status
  gpu_occupancy_lifecycle.sh run -- FORMAL_TRAINING_COMMAND [ARGS...]

Always use `run -- ...` for formal training. It stops the holder first and
restores it after success, errors, Ctrl-C, TERM, or HUP. Restoration retries
until one manager and all expected GPUs pass the configured thresholds.
EOF
}

command_name="${1:-}"
case "${command_name}" in
    stop)
        shift
        (( $# == 0 )) || { usage >&2; exit 2; }
        if /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" active; then
            printf 'Persistent guard is active; use run -- COMMAND for a reserved GPU handoff.\n' >&2
            exit 2
        fi
        stop_holder
        ;;
    start)
        shift
        (( $# == 0 )) || { usage >&2; exit 2; }
        /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" start
        ;;
    status)
        shift
        (( $# == 0 )) || { usage >&2; exit 2; }
        if /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" active; then
            /usr/bin/python "${WORKSPACE_ROOT}/gpu_occupancy_guard.py" status
            nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
        else
            show_status
        fi
        ;;
    run)
        shift
        [[ "${1:-}" == '--' ]] && shift
        run_formal_command "$@"
        ;;
    -h|--help|help|'')
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
