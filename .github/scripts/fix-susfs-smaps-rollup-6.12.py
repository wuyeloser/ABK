#!/usr/bin/env python3
"""Adapt the SUSFS rollup filter to the android16-6.12 VMA iterator."""
import re
import sys
from pathlib import Path


def fix(path: Path) -> None:
    text = path.read_text()
    start = text.index("static int show_smaps_rollup(")
    end = text.index("\nstatic ", start + 1)
    body = text[start:end]
    marker = "/* ABK: filter SUS_MAP in all rollup accounting paths. */"
    reject = path.with_suffix(path.suffix + ".rej")
    if marker not in body:
        if "SUSFS_IS_INODE_SUS_MAP" in body:
            raise RuntimeError("Existing rollup filter needs review")
        pattern = r"(?m)^([ \t]*)smap_gather_stats\(vma, &mss, (0|last_vma_end)\);$"
        if len(re.findall(pattern, body)) != 3:
            raise RuntimeError("Unexpected rollup accounting layout")

        def replacement(match: re.Match) -> str:
            indent, offset = match.groups()
            return (f"{indent}{marker}\n"
                    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
                    f"{indent}if (!vma->vm_file ||\n"
                    f"{indent}    !SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n"
                    "#endif\n"
                    f"{indent}\tsmap_gather_stats(vma, &mss, {offset});")

        body = re.sub(pattern, replacement, body)
        text = text[:start] + body + text[end:]
        path.write_text(text)
    if body.count(marker) != 3 or body.count("SUSFS_IS_INODE_SUS_MAP") != 3:
        raise RuntimeError("Incomplete rollup filter")
    if reject.exists():
        rejected = reject.read_text()
        if (rejected.count("@@") != 4 or "show_smaps_rollup" not in rejected
                or "smap_gather_stats(priv, vma, &mss)" not in rejected
                or "SUSFS_IS_INODE_SUS_MAP" not in rejected):
            raise RuntimeError("Unrecognized reject: preserve for review")
        reject.unlink()
    print("SUSFS_ROLLUP_612_VERIFIED: three accounting paths filtered; iterator and locking preserved")


if __name__ == "__main__":
    fix(Path(sys.argv[1]))
