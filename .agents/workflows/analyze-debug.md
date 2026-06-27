---
description: Tracing function calls and analyzing engine logic through IDA pseudo-code. Use when you need to understand how a function behaves, find a bug, or follow a call chain.
---

# Analyzing and Debugging

## Goal
Understand engine behavior, find the root cause of a bug, or trace a call chain.

## Code Sources

| Architecture | Directory | Purpose |
|-------------|-----------|---------|
| Generated Headers | `mcpe16-arm64-headers/` | Auto-generated C++ headers containing class definitions, mangled symbols, virtual slot indices, and known method constants. |
| ARM32 | `mcpe16-arm32/` | Class pseudo-code from IDA |
| ARM64 | `mcpe16-arm64/` | Class pseudo-code from IDA |
| Global functions | `mcpe16-arm32/__sub__.c` or `mcpe16-arm64/__sub__.c` | JNI exports, entry points, functions without a class |
| Trampolines | `*-thunks.c` | Only when analyzing a specific jump address |

## Steps

1. **Find the class** — file is named after the class, e.g. `Zombie.c` or `AppPlatform_android.c`.
2. **Find the function** — search by method name or mangled symbol (`_ZN...`).
3. **Trace calls** — if you encounter `sub_XXXXXXXX`, look it up in `__sub__.c`. For virtual calls, check the slot offset in `mcpe16-vtable.md`.
4. **Check both architectures** — ARM32 and ARM64 may differ. ARM64 pseudo-code is usually cleaner.
5. **Account for `this`** — in IDA pseudo-code, `this` is the first argument.

## Useful Patterns

- Global variables are often in `__sub__.c` as `local static` or via guard variables (`_ZGVZ...`).
- Inlined functions may have no symbol — look for matching patterns in neighboring files.
- To identify what stands behind a virtual call, find the slot in `mcpe16-vtable.md`.
