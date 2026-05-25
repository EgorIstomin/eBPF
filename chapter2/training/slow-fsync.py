#!/usr/bin/env python3

from bcc import BPF
from time import sleep

program = r"""
#include <uapi/linux/ptrace.h>

BPF_HASH(start, u32, u64);

int trace_fsync_enter(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();

    start.update(&pid, &ts);
    return 0;
}

int trace_fsync_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *tsp;
    u64 delta;
    char comm[16];

    tsp = start.lookup(&pid);
    if (tsp == 0) {
        return 0;
    }

    delta = bpf_ktime_get_ns() - *tsp;
    start.delete(&pid);

    if (delta < 100000000) {
        return 0;
    }

    bpf_get_current_comm(&comm, sizeof(comm));

    bpf_trace_printk("PID=%d COMM=%s fsync=%lld ms\\n",
                     pid, comm, delta / 1000000);

    return 0;
}
"""

b = BPF(text=program)

fsync = b.get_syscall_fnname("fsync")

b.attach_kprobe(event=fsync, fn_name="trace_fsync_enter")
b.attach_kretprobe(event=fsync, fn_name="trace_fsync_return")

print("Tracing slow fsync() calls > 100ms... Ctrl-C to stop.")

b.trace_print()