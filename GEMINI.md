# Workspace Guide: Minecraft Bedrock Edition 1.16.201 (Inner Core)

This workspace contains reverse-engineered code for Minecraft: Bedrock Edition 1.16.201, used for writing C++ mods for Inner Core. 
**Our C++ mod code must be placed in the `modules/` directory.**

## 📂 Architecture
- `mcpe16-arm32/` and `mcpe16-arm64/`: IDA pseudo-code, split by classes.
- `symbols/`: `.h` header files. Contain demangled signatures and mangled symbols **only for ARM32**.
- `mcpe16-vtable.md`: Virtual method table (vtable) offsets.
- `libmcpe16-arm64-symbols.txt`: Massive dump where mangled symbols **exclusively for ARM64** are stored.
- `mcpe16-init-timings.txt`: Initialization timings.

## 📄 Specific Files
- **`__sub__.c`**: A file where IDA places all independent global functions, JNI exports, entry points (including `android_main`), and everything not bound to specific structures/classes. If a function doesn't have a class, it's located here.
- **`*thunks.c` (`mcpe16-arm32-thunks.c` / `mcpe16-arm64-thunks.c`)**: Contain tiny trampoline functions. Used only when calling a specific thunk address or analyzing a jump is required.

## 🏗️ Core Engine Instances
- **`MinecraftGame`**: The massive central engine state machine. It orchestrates all global initialization steps and the main update loop.
- **`ClientInstance`**: Encapsulates the local player's game state, UI (Hummingbird/Gameface), and rendering context. Easily retrieved globally via `GlobalContext::getMinecraftClient()` (requires `#include <innercore/global_context.h>`).
  * **Tip**: Other core instances (`Minecraft`, `Level`, `LocalPlayer`, `AppPlatform`) are also available through the `GlobalContext` namespace in Inner Core's API.

## 🚫 Files to Ignore
Strictly ignore databases (`.idb`, `.i64`), massive monolithic code dumps (`.so.c`), scripts (`ida_dumper.py`), and Java sources. They are not used.

## 🛠️ Workflows
Depending on the objective, the workflow varies. We primarily work with symbols, but different tasks require different approaches:
- **Analyzing and Debugging**: Trace function calls and logic through `mcpe16-arm32/` or `mcpe16-arm64/` (and `__sub__.c` for globals) to find bugs or understand engine behavior.
- **Hooking and Memory Patching**: Find the target mangled symbol (starts with `_Z`). For ARM32 use `symbols/`, for ARM64 use `libmcpe16-arm64-symbols.txt`. If it's a virtual function, get its offset from `mcpe16-vtable.md`. Write the C++ hook using `HookManager::addCallback` and `LAMBDA` in `modules/`. Example: `HookManager::addCallback(SYMBOL("mcpe", "_Z..."), LAMBDA((void* self) { ... }, ), HookManager::LISTENER | HookManager::CALL);`
- **Reversing and Restoring Structures**: Do **not** recreate C++ classes with raw paddings (like `char pad[123]`) to avoid arm32/arm64 alignment crashes. Instead, use the Data-Driven approach via `generic/offsets_macro.h` to safely access fields. Example: `HZ_DECL_OFFSETS_FOR(MyStruct) { HZ_DECL_OFFSET(0x04, myField); HZ_DECL_SIZE(120); };`. Always declare proper C++ classes and structures instead of working with raw memory (`void*`).

## ⚙️ Inner Core / Horizon C++ API
- **Includes**: Headers are searched in `stdincludes/`. Write paths without roots: `#include <hook.h>`, `#include <innercore/global_context.h>`.
- **STL / Standard Library**: Always `#include <stl.h>` for standard library needs and use its provided structures (e.g., `stl_string`).
- **Method Linking**: **Methods link with the game library automatically!** You do **not** need `LINK_RESULT_METHOD` or `STATIC_SYMBOL_WITH_RESULT` for standard methods. Simply write the proper C++ declaration (e.g., `const ActorDefinitionIdentifier& getActorIdentifier() const;`) and the linker will resolve it.
- **Destructors**: If a destructor needs to be manually linked, use the `LINK_DESTRUCTOR` macro inside the class declaration. Example: `LINK_DESTRUCTOR(Value, "_ZN4Json5ValueD1Ev");`. Do **not** use `STATIC_SYMBOL_WITH_RESULT` for destructors.
- **Calling Originals**: To call an original method, just declare the class and call it (e.g., `zombie->die(damageSource)`). If you are inside a vtable hook and want to avoid virtual recursion, call the method statically: `zombie->Zombie::die(damageSource);`.
- **C++ Standards**: 
  - `arm32`: C++11
  - `arm64`: C++17. Macro for check: `#if defined(ARM64) || defined(_M_ARM64) || defined(__aarch64__)`.

- **Hooks (`#include <hook.h>`)**: 
  - The `HookManager::CallbackController* controller` argument must **ONLY** be added to your lambda if the `HookManager::CONTROLLER` flag is passed! 
  - If you use default flags (`HookManager::LISTENER | HookManager::CALL`), your lambda arguments must exactly match the target function arguments. Adding `controller` without the flag shifts arguments and causes crashes.
  - **CONTROLLER & RESULT**: When using `HookManager::CONTROLLER` to intercept/modify execution:
    - Use `HookManager::CONTROLLER | HookManager::CALL | HookManager::LISTENER | HookManager::RESULT`.
    - `CALL` runs *before* the target. If the condition isn't met, do **not** call `controller->call()`. The engine will naturally call the original function.
    - If you want to prevent/replace it, use `controller->replace()` and return the result from the lambda.
    - There is no hidden `result` pointer passed as an argument in AAPCS for `unique_ptr` when using HookManager! The return value is just the return type of `controller->call<ReturnType>(args...)` and the lambda itself.
  - **Lambdas**: Write most hook logic directly inside the `LAMBDA` instead of extracting it to separate functions, avoiding return type issues.
