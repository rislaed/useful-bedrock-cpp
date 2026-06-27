---
description: Reversing and restoring engine structs and classes without raw paddings. Use when you need to safely access a class field by offset or declare a structure for ARM32/ARM64.
---

# Reversing and Restoring Structures

## Goal
Safely access engine class fields without creating C++ classes with raw paddings.

## Rule: Don't Do This

```cpp
// ❌ BAD — paddings break between arm32/arm64
class Zombie {
	char pad[123];
	int health;
};
```

## Rule: Use offsets_macro.h

```cpp
// ✅ GOOD — Data-Driven approach
#include <generic/offsets_macro.h>

HZ_DECL_OFFSETS_FOR(Zombie) {
	HZ_DECL_OFFSET(0x04, health);
	HZ_DECL_SIZE(120);
};

// Usage:
auto health = Zombie::Offsets::health(zombiePtr);
```

## Steps

1. **Find offsets** in IDA pseudo-code (`mcpe16-arm64/` for ARM64, `mcpe16-arm32/` for ARM32).
   - Offsets may differ between ARM32 and ARM64 — verify both.
2. **Declare the C++ class** normally (no paddings), with only the methods you need.
3. **For fields** — use `HZ_DECL_OFFSETS_FOR` + `HZ_DECL_OFFSET`.
4. **For methods** — just declare with the correct signature; the linker resolves automatically.
5. **For destructors** — if explicit linking is needed: `LINK_DESTRUCTOR(MyClass, "_ZN...D1Ev");` inside the class.

## Declaration Examples

```cpp
// Regular class with methods (auto-linked):
class ActorDefinitionIdentifier {
public:
	const std::string& getFullName() const; // _ZNK25ActorDefinitionIdentifier11getFullNameEv
};

// With manually linked destructor:
class Json::Value {
public:
	LINK_DESTRUCTOR(Value, "_ZN4Json5ValueD1Ev");
	std::string asString() const;
};
```

## Resources
- Field offsets: `mcpe16-arm64/ClassName.c` — search for `*(this + 0xXX)` patterns
- Vtable slots: `mcpe16-vtable.md`
- Engine headers: `mcpe16-arm64-headers/` — auto-generated C++ headers containing:
  - Class definitions and dummy enums for nested types
  - Mangled symbols (`// _ZN...`)
  - Virtual method slot indices (`// slot N:`)
  - Known constant return values (`= true`, `= 0x10`)
