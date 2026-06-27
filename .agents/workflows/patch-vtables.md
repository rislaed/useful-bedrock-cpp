---
description: Patching virtual method tables (VTable) for individual instances to create custom entities or items without hooking globally.
---

# Patching Instance VTables

## Goal & When to Use
**Trigger this workflow when:**
You need to modify the behavior of a **specific instance** of a class (e.g., a custom entity like `UncleZot`, or a custom item/block), rather than hooking a method globally for all instances.
By cloning the original class's virtual table (VTable) and replacing specific methods, you can assign this new VTable to your custom instance. This allows it to run your custom C++ logic while leaving vanilla instances unaffected.

## Required Includes
```cpp
#include <symbol.h>
#include <horizon/innercore/vtable.h> // Contains getVtableOffset and VTABLE_SET
```

## Steps to Patch a VTable

### Step 1: Declare VTable Storage
The original engine VTable resides in **read-only memory (.rodata)**, so we cannot patch it directly without causing a crash. Instead, we must create our own copy of the table in RAM.

Declare a static array to hold the cloned VTable, and a pointer offset by 2 (to skip RTTI and offset-to-top).
```cpp
// Array for the cloned vtable (with a safe margin, e.g. 500 pointers)
static void* mobVtableBase[500];

// The actual vptr that instances will point to (index 2)
static void** mobVtable = &mobVtableBase[2]; 

static bool isVtableInitialized = false;
```

### Step 2: Write Custom Methods
Write your replacement methods as static or free functions. Make sure the first argument is a pointer to the instance (`this`).

```cpp
// Custom die method
void Custom_die(Mob* mob, const ActorDamageSource& source) {
    // 1. Call original method statically to avoid infinite recursion
    mob->Mob::die(source);

    // 2. Add custom logic
    Logger::debug("CustomEntity", "Entity has died!");
}

// Custom tick method
void Custom_normalTick(Actor* actor) {
    actor->Actor::normalTick();
    // Custom logic...
}
```

### Step 3: Initialize and Patch Our Cloned VTable
Create an initialization function that runs exactly once. It will copy the original VTable and patch it using `VTABLE_SET` from `<horizon/innercore/vtable.h>`.

```cpp
void initmobVtable() {
    if (isVtableInitialized) return;

    // 1. Find the original VTable symbol (e.g. for Mob)
    void** mobVtable = (void**) SYMBOL("mcpe", "_ZTV3Mob");

    // 2. Copy the entire VTable to our storage
    memcpy(mobVtableBase, mobVtable, sizeof(void*) * 500);

    // 3. Patch specific methods in OUR copy using VTABLE_SET
    // Syntax: VTABLE_SET(mobVtablePtr, ClassName, MethodSymbol) = (void*) &MyFunction;

    VTABLE_SET(mobVtable, _ZTV3Mob, _ZN3Mob3dieERK17ActorDamageSource) = (void*) &Custom_die;
    VTABLE_SET(mobVtable, _ZTV3Mob, _ZN5Actor10normalTickEv) = (void*) &Custom_normalTick;

    isVtableInitialized = true;
}
```
*Note: `VTABLE_SET` automatically searches the original VTable to find the slot index of the target method, making your code safe from architecture-specific index changes!*

### Step 4: Patching the Instance (Changing the `vptr`)
Because we cannot modify the original VTable in memory, we must modify the **instance itself**. Every C++ object with virtual methods stores a pointer to its VTable as its very first member (the `vptr`). 

When your custom instance is created, you simply swap this pointer to your custom VTable!

```cpp
// Example inside an ActorFactory hook
Actor* myEntity = (Actor*) originalFactoryCall(...);

if (myEntity /* check if it's your custom entity type */) {
    initmobVtable();

    // Patch the instance by swapping its vptr (the first 4/8 bytes of the object)
    *(void***) myEntity = mobVtable;
}
```

## Calling Virtual Methods Dynamically
Sometimes you need to call a virtual method on an engine instance, but you don't want to recreate the entire C++ class structure. You can do this dynamically using `VTABLE_FIND_OFFSET` and `VTABLE_CALL`.

```cpp
void callDieDynamically(Mob* mob, const ActorDamageSource& source) {
    // 1. Find the offset dynamically and cache it in a static variable 'dieOffset'
    VTABLE_FIND_OFFSET(dieOffset, _ZTV3Mob, _ZN3Mob3dieERK17ActorDamageSource);

    // 2. Call the method through the instance's vtable!
    // Syntax: VTABLE_CALL<ReturnType>(offset, instancePtr, arg1, arg2...)
    VTABLE_CALL<void>(dieOffset, mob, source);
}
```
This looks up the offset once and uses it to call the method directly from the object's `vptr`, making it highly resilient to engine updates!

## Real-World Examples in Inner Core

If you look at Inner Core's source code, you will see this exact pattern used extensively to create custom engine objects. For example, Inner Core uses `VTABLE_SET` to patch `BlockLegacy`, `Item`, and `FlameParticle` internally to inject its own logic:

```cpp
VTABLE_SET(vtable, _ZTV13FlameParticle, _ZN13FlameParticle10normalTickEv) = (void*) &normalTick;
VTABLE_SET(vtable, _ZTV13FlameParticle, _ZN13FlameParticle10tessellateERK21ParticleRenderContext) = (void*) &tessellate;
```

Because this macro is exposed in `stdincludes/horizon/innercore/vtable.h`, we can use the exact same highly robust approach to patch our own custom entities (like `UncleZot`) or any other engine instances directly in our C++ modules!

## Resources
- **VTable Symbols**: You can find the original VTable symbols in IDA (e.g. search for `_ZTV` + class name).
- **Method Symbols**: Used in `VTABLE_SET`, found in IDA or `mcpe16-arm64-headers/`.
- **`innercore/vtable.h`**: Located in `stdincludes/horizon/innercore/vtable.h`. Provides `getVtableOffset(vtableName, funcName)` and `VTABLE_SET`.
