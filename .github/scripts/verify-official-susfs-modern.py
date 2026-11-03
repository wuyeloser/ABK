#!/usr/bin/env python3
"""Verify upstream SUSFS direct-hook integration before skipping legacy rewrites."""

import re
import sys
from pathlib import Path


def verify(root: Path) -> None:
    def read(name: str) -> str:
        path = root / name
        if not path.is_file():
            raise SystemExit(f"Modern SUSFS missing source: {path}")
        return path.read_text()

    def require(name: str, *markers: str) -> str:
        text = read(name)
        for marker in markers:
            if marker not in text:
                raise SystemExit(f"Modern SUSFS missing {marker!r} in {name}")
        return text

    rejects = list(root.rglob("*.rej"))
    if rejects:
        raise SystemExit(f"Modern SUSFS has rejected patches: {rejects}")

    require("Kbuild", "infra/symbol_resolver.o", "preinit/preinit.o", "preinit/blob.o")
    require("core/init.c", "ksu_init_symbol_resolver();", "ksu_preinit_init();", "ksu_preinit_exit();")
    runtime = require(
        "runtime/ksud_integration.c",
        "DEFINE_STATIC_KEY_TRUE(is_first_zygote);",
        "static_branch_disable(&is_first_zygote);",
        "int ksu_handle_execveat_ksud(int *fd",
    )
    require("runtime/ksud.h", "int ksu_handle_execveat_ksud(int *fd")
    if "ksu_clear_task_tracepoint_flag_if_needed(" in read("hook/setuid_hook.c"):
        raise SystemExit("Modern SUSFS retains a call into removed tracepoint hooks")
    require("feature/sucompat.c", '#include "util.h"', "ksu_adb_root_handle_execveat(filename->name")
    require("include/util.h", "userspace_stack_buffer(")
    hide = require(
        "feature/selinux_hide.c",
        "void ksu_selinux_hide_handle_second_stage()",
        "void ksu_selinux_hide_handle_post_fs_data()",
    )
    for name in ("ksu_selinux_hide_handle_second_stage", "ksu_selinux_hide_handle_post_fs_data"):
        match = re.search(r"void\s+" + name + r"\s*\([^)]*\)\s*\{([^}]+)", hide)
        if not match or "fake_status" not in match.group(1):
            raise SystemExit(f"Modern SUSFS missing real lifecycle handler: {name}")
    require("infra/symbol_resolver.c", "int __nocfi ksu_lookup_kernel_symbols(")
    preinit = require(
        "preinit/preinit.c",
        "int ksu_setup_preinit_file(",
        "int ksu_preinit_handle_post_execveat(",
        "fd_install(fd, file);",
        "ksu_close_fd(*preinit_fd);",
    )
    if "ksu_syscall_table[" in preinit:
        raise SystemExit("Modern SUSFS preinit still relies on the removed syscall table")
    if "ksu_preinit_release();" not in runtime:
        raise SystemExit("Modern SUSFS runtime lost preinit runner release")
    print("MODERN_OFFICIAL_SUSFS_VERIFIED: upstream direct hooks, preinit and symbol resolver preserved")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
