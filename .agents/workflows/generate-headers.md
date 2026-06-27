---
description: Regenerating ARM64 headers from symbols and vtable. Use when you need to update mcpe16-arm64-headers/ after modifying generate_headers.py or constants.
---

# Generating ARM64 Headers

## Goal
Update the auto-generated C++ headers in `mcpe16-arm64-headers/` from symbols, vtable, and constants.

## Data Sources

| File | Purpose |
|------|---------|
| `libmcpe16-arm64-symbols.txt` | All ARM64 mangled symbols |
| `libmcpe16-arm64-vtable.md` | Vtable slots and offsets |
| `libmcpe16-arm64-constants.json` | Constant return values for methods |
| `generate_headers.py` | The generation script |

## Run

```powershell
python generate_headers.py mcpe16-arm64
```

Generation takes ~2 minutes. Output: `mcpe16-arm64-headers/*.h`.

## Script Architecture

1. Loads constants from `libmcpe16-arm64-constants.json`
2. Parses vtable from `libmcpe16-arm64-vtable.md`
3. Builds the inheritance tree
4. Resolves pure virtual methods
5. Reads symbols from `libmcpe16-arm64-symbols.txt`
6. Generates headers into `mcpe16-arm64-headers/`

## Constants

- File format: `libmcpe16-arm64-constants.json` next to the script
- Constant methods (`_ZNK...`) are annotated with `= value` in the comment: `bool useNewAi() const; // slot 339: _ZNK6Zombie8useNewAiEv = true`
- Bool constants: `1` → `true`, `0` → `false`

## Key Header Features

- **Dummy enums**: unknown nested types are generated as `enum class Foo : int;` — sufficient for casting to int
- **Virtual slots**: annotated with `// slot N: _ZN...`
- **Commented duplicates**: C2 constructors and D2 destructors are commented out (`// ClassName(); // _ZN...C2Ev`)
- **local static**: annotated as `// local static MethodName(...); // _ZZ...`
- **Static fields**: `static void* FIELD_NAME; // _ZN...E`
