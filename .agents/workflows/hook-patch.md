---
description: Writing C++ hooks to intercept engine methods via HookManager. Use when you need to intercept a method call, modify behavior, or subscribe to an engine event.
---

# Hooking and Memory Patching

## Goal
Intercept an engine method call, modify its behavior, or observe it.

## Step 1 — Find the Symbol

Use the auto-generated headers in `mcpe16-arm64-headers/` to find the target. These headers contain:
- Mangled symbols (e.g., `// _ZN...`)
- Virtual method slot indices (`// slot N:`)
- Constant return values for some methods (`= true`, `= 0x1000`)
- Complete class definitions with dummy enums and nested structures

Example from `mcpe16-arm64-headers/Zombie.h`:

```cpp
// In mcpe16-arm64-headers/Zombie.h:
virtual void die(ActorDamageSource const&); // slot 236: _ZN6Zombie3dieERK17ActorDamageSource
bool useNewAi() const;                      // _ZNK6Zombie8useNewAiEv = true
```

- Prefer `_ZNK` symbols for `const` methods — they are more precise.
- For virtual functions: the slot number is in the `// slot N:` comment; use it for vtable hooks if needed.
- For ARM32: use `symbols/*.h` headers instead.

## Step 2 — Pick Flags

| Goal | Flags |
|------|-------|
| Observe only | `HookManager::LISTENER \| HookManager::CALL` |
| Intercept and replace | `HookManager::CONTROLLER \| HookManager::CALL \| HookManager::LISTENER \| HookManager::RESULT` |

> **IMPORTANT**: Add `HookManager::CallbackController* controller` to the lambda ONLY when the `CONTROLLER` flag is passed! Without it, arguments shift and you get a crash.

## Step 3 — Write the Hook

```cpp
#include <hook.h>
#include <innercore/global_context.h>

// Simple listener:
HookManager::addCallback(
	SYMBOL("mcpe", "_ZN6Zombie3dieERK17ActorDamageSource"),
	LAMBDA((Zombie* self, ActorDamageSource const& src) {
		// your code
	},),
	HookManager::LISTENER | HookManager::CALL
);

// With result interception (CONTROLLER):
HookManager::addCallback(
	SYMBOL("mcpe", "_ZNK6Zombie8useNewAiEv"),
	LAMBDA((HookManager::CallbackController* controller, Zombie* self) {
		controller->replace();
		return true; // override return value
	},),
	HookManager::CONTROLLER | HookManager::CALL | HookManager::LISTENER | HookManager::RESULT
);
```

## Step 4 — Calling the Original

- From a regular hook: just call the method — `zombie->die(src)`.
- From a vtable hook (to avoid recursion): call statically — `zombie->Zombie::die(src)`.
- With `CONTROLLER`: `controller->call<ReturnType>(args...)`.

## Where to Write Code
All mod code goes in `modules/`. No need for `LINK_RESULT_METHOD` or `STATIC_SYMBOL_WITH_RESULT` — methods link automatically.

## C++ Standards
- ARM32: C++11
- ARM64: C++17. Check: `#if defined(ARM64) || defined(_M_ARM64) || defined(__aarch64__)`
