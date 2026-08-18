"""Repair the 'book' field in existing ChromaDB metadata.

Some records have wrong values in the 'book' field (chapter names instead of
book titles). This script fixes them by looking up the correct book title
from config.SOURCES based on the source_name field.

Usage:
    python repair_book_field.py          # dry-run, show what would change
    python repair_book_field.py --apply  # actually fix the data
"""

import sys
import os
import config
from store import get_collections

# Build source_name -> correct book title mapping
SOURCE_BOOK_MAP = {}
for src in config.SOURCES:
    title = src.get("title", "")
    name = src.get("name", "")
    if title and name:
        SOURCE_BOOK_MAP[name] = title


def repair(apply: bool = False):
    """Scan both collections and fix wrong 'book' values."""
    sec_coll, chk_coll = get_collections()
    fixed = 0

    for label, coll in [("sections", sec_coll), ("chunks", chk_coll)]:
        total = coll.count()
        if total == 0:
            continue

        ids_to_fix = []
        metas_to_fix = []

        batch = 5000
        for offset in range(0, total, batch):
            result = coll.get(limit=batch, offset=offset, include=["metadatas"])
            for id_, meta in zip(result["ids"], result["metadatas"]):
                if not meta:
                    continue
                src_name = meta.get("source_name", "")
                current_book = meta.get("book", "")
                correct_book = SOURCE_BOOK_MAP.get(src_name, "")

                if correct_book and current_book != correct_book:
                    new_meta = dict(meta)
                    new_meta["book"] = correct_book
                    ids_to_fix.append(id_)
                    metas_to_fix.append(new_meta)

        if ids_to_fix:
            print(f"  {label}: {len(ids_to_fix)} records to fix "
                  f"(out of {total})")
            fixed += len(ids_to_fix)
            if apply:
                # Update in batches
                for i in range(0, len(ids_to_fix), batch):
                    end = min(i + batch, len(ids_to_fix))
                    coll.update(ids=ids_to_fix[i:end],
                               metadatas=metas_to_fix[i:end])
                print(f"    -> fixed {len(ids_to_fix)} records")
        else:
            print(f"  {label}: all {total} records already correct")

    if apply:
        print(f"\nTotal fixed: {fixed} records")
    else:
        print(f"\nDry run. Use --apply to actually fix {fixed} records.")


def main():
    apply = "--apply" in sys.argv
    repair(apply=apply)


if __name__ == "__main__":
    main()
