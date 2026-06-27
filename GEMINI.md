# Workspace Guide: Minecraft Bedrock Edition 1.16.201 (Inner Core)

This workspace contains reverse-engineered code for Minecraft: Bedrock Edition 1.16.201, used for writing C++ mods for Inner Core. 
**Our C++ mod code must be placed in the `modules/` directory.**

## 📂 Architecture
- `mcpe16-arm32/` and `mcpe16-arm64/`: IDA pseudo-code, split by classes. Very useful for tracing engine logic and call hierarchies.
- `mcpe16-arm64-headers/`: Auto-generated C++ headers containing complete class structures, virtual method slots, and mangled symbols. This is the primary source of truth for ARM64 types and definitions.
- `mcpe16-init-timings.txt`: Initialization timings.

## 📄 Specific Files
- **`__sub__.c`**: A file where IDA places all independent global functions, JNI exports, entry points (including `android_main`), and everything not bound to specific structures/classes. If a function doesn't have a class, it's located here.
- **`*thunks.c` (`mcpe16-arm32-thunks.c` / `mcpe16-arm64-thunks.c`)**: Contain tiny trampoline functions. Used only when calling a specific thunk address or analyzing a jump is required.

## 🏗️ Core Engine Instances
- **`MinecraftGame`**: The massive central engine state machine. It orchestrates all global initialization steps and the main update loop.
- **`ClientInstance`**: Encapsulates the local player's game state, UI (Hummingbird/Gameface), and rendering context. Easily retrieved globally via `GlobalContext::getMinecraftClient()` (requires `#include <innercore/global_context.h>`, see `stdincludes/horizon/innercore/global_context.h` for global instances).
  * **Tip**: Other core instances (`Minecraft`, `Level`, `LocalPlayer`, `AppPlatform`) are also available through the `GlobalContext` namespace in Inner Core's API.

## 🚫 Files to Ignore
Strictly ignore databases (`.idb`, `.i64`), massive monolithic code dumps (`.so.c`), scripts (`ida_dumper.py`), and Java sources. They are not used.

## ⚙️ Inner Core / Horizon C++ API
- **Includes**: Headers are searched in `stdincludes/`. Write paths without roots: `#include <hook.h>`, `#include <innercore/global_context.h>`.
- **STL / Standard Library**: Always `#include <stl.h>` for standard library needs and use its provided structures (e.g., `stl_string`).
- **Method Linking**: **Methods link with the game library automatically!** You do **not** need `LINK_RESULT_METHOD` or `STATIC_SYMBOL_WITH_RESULT` for standard methods. Simply write the proper C++ declaration (e.g., `const ActorDefinitionIdentifier& getActorIdentifier() const;`) and the linker will resolve it.
- **Destructors**: If a destructor needs to be manually linked, use the `LINK_DESTRUCTOR` macro inside the class declaration. Example: `LINK_DESTRUCTOR(Value, "_ZN4Json5ValueD1Ev");`. Do **not** use `STATIC_SYMBOL_WITH_RESULT` for destructors.
- **Calling Originals**: To call an original method, just declare the class and call it (e.g., `zombie->die(damageSource)`). If you are inside a vtable hook and want to avoid virtual recursion, call the method statically: `zombie->Zombie::die(damageSource);`.
- **C++ Standards**: 
  - `arm32`: C++11
  - `arm64`: C++17. Macro for check: `#if defined(ARM64) || defined(_M_ARM64) || defined(__aarch64__)`.

## 🛠️ Tool Usage
- **Reading files**: Do NOT use `cat` in PowerShell to read files (especially multiple files like `cat file1 file2`, which causes parameter binding errors). ALWAYS use the specific `view_file` tool for reading and `grep_search` for searching.
