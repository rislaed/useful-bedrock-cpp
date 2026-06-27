---
description: Reversing and restoring engine structs and classes without raw paddings. Use when you need to safely access a class field by offset or declare a structure for ARM32/ARM64.
---

# Hooking and Memory Patching

## Goal & When to Use
**Trigger this workflow when:**
You need to read or write a specific field inside an engine class (e.g., getting `health` from an `Actor`, or reading `speed` from a `Mob`), and you found the memory offset of that field in IDA.
This workflow shows how to access these fields safely across different game architectures (ARM32/ARM64) without hardcoding raw byte arrays (`char pad[...]`), which is dangerous and breaks between platforms.

## Rule: Don't Do This

```cpp
// ❌ BAD — paddings break between arm32/arm64
class Zombie {
	char pad[123];
	int health;
};
```

## Rule: Use offsets_macro.h

Cross-platform field access is achieved through Inner Core's macro system, which automatically generates padding based on offsets defined for a specific architecture.

### Step 1: Declare Offsets
Offsets must be declared inside the `__offsets` namespace using `HZ_DECL_OFFSETS_FOR`. Since offsets differ between ARM32 and ARM64, you must separate them using compiler directives (`#ifdef ARM64`).

```cpp
// ✅ GOOD — Data-Driven approach
#include <generic/offsets_macro.h>

namespace __offsets {
#if defined(ARM64) || defined(_M_ARM64) || defined(__aarch64__)
	HZ_DECL_OFFSETS_FOR(Zombie) {
		HZ_DECL_OFFSET(0x08, health);
		HZ_DECL_SIZE(136);
	};
	// If the class is inside a namespace (e.g., mce::UUID):
	HZ_DECL_OFFSETS_FOR_NS(mce) {
		HZ_DECL_OFFSETS_FOR(UUID) {
			HZ_DECL_OFFSET(0x04, data);
			HZ_DECL_SIZE(16);
		};
	};
#else
	// ARM32 Offsets
	HZ_DECL_OFFSETS_FOR(Zombie) {
		HZ_DECL_OFFSET(0x04, health);
		HZ_DECL_SIZE(120);
	};
	HZ_DECL_OFFSETS_FOR_NS(mce) {
		HZ_DECL_OFFSETS_FOR(UUID) {
			HZ_DECL_OFFSET(0x04, data);
			HZ_DECL_SIZE(16);
		};
	};
#endif
}
```

### Step 2: Declare the Structure
The structure itself is declared using `HZ_DECL_PLAIN_STRUCT` (or `HZ_DECL_VTABLE_STRUCT` if the class has virtual methods). Fields are added using `HZ_DECL_FIELD`, passing a sequential index. Finally, `HZ_DECL_STRUCT_SIZE_PAD` is called with the total field count.

```cpp
class Zombie {
public:
	// If the class has a vtable (virtual methods), use HZ_DECL_VTABLE_STRUCT.
	// Otherwise, use HZ_DECL_PLAIN_STRUCT.
	HZ_DECL_VTABLE_STRUCT(Zombie);

	// Fields: HZ_DECL_FIELD(Index, Type, Name)
	HZ_DECL_FIELD(0, int, health);
	HZ_DECL_FIELD(1, float, speed);

	// Final padding: pass the total number of fields
	HZ_DECL_STRUCT_SIZE_PAD(2);

	// Regular methods (linked automatically)
	virtual void die(ActorDamageSource const&);
	bool useNewAi() const;
};

// For classes inside a namespace:
namespace mce {
	class UUID {
	public:
		// Notice how we don't pass 'mce::UUID', just 'UUID'.
		// The macro uses the current C++ namespace automatically.
		HZ_DECL_PLAIN_STRUCT(UUID);
		HZ_DECL_FIELD(0, uint64_t, data);
		HZ_DECL_STRUCT_SIZE_PAD(1);
	};
}
```

## Steps

1. **Find offsets** in IDA pseudo-code (`mcpe16-arm64/` for ARM64, `mcpe16-arm32/` for ARM32).
   - Offsets and sizes differ between architectures. Record both.
2. **Declare offsets** in `namespace __offsets` separated by `#if defined(ARM64)`.
3. **Declare the C++ class** using `HZ_DECL_VTABLE_STRUCT` or `HZ_DECL_PLAIN_STRUCT`.
4. **Declare fields** using `HZ_DECL_FIELD(Idx, Type, Name)`.
5. **Declare size padding** using `HZ_DECL_STRUCT_SIZE_PAD(FieldCount)`.
6. **For methods** — just declare with the correct signature; the linker resolves them automatically.
7. **For destructors** — if explicit linking is needed: `LINK_DESTRUCTOR(MyClass, "_ZN...D1Ev");` inside the class.

> **IMPORTANT EXCEPTION (No Fields / Pointer Only)**:
> If a class has **no fields** that you need to access, AND you **only use it via pointers or references** (you don't allocate it on the stack or inherit from it), **do NOT use the macros**. Just declare a standard C++ class. The compiler only needs the methods.

## Resources
- Field offsets: `mcpe16-arm64/ClassName.c` — search for `*(this + 0xXX)` patterns
- Vtable slots: `mcpe16-vtable.md`
- Engine headers: `mcpe16-arm64-headers/` — auto-generated C++ headers containing:
  - Class definitions and dummy enums for nested types
  - Mangled symbols (`// _ZN...`)
  - Virtual method slot indices (`// slot N:`)
  - Known constant return values (`= true`, `= 0x10`)
