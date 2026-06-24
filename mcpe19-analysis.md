# Анализ mcpe19: файлы > 512KB для Inner Core + Rhino + JNI

## Полезные данные: размеры классов

> Определены по максимальному смещению `this + N` в конструкторах и методах.

### Иерархия сущностей

```
Actor:     max_offset ≈ 2032   → sizeof(Actor) ≥ 2040 байт
  └─ Mob:  max_offset ≈ 1784   → sizeof(Mob) ≥ 1792 байт  
              (Mob начинается после Actor, +Actor_size)
  └─ Player: max_offset ≈ 7724 → sizeof(Player) ≥ 7732 байт
```

**Ключевые поля Actor** (из конструктора):
| Смещение | Поле/Тип |
|----------|----------|
| +0 | vtable ptr |
| +8 | EntityContext* (entity registry) |
| +24 | byte flags |
| +224 | float[3] — position? (xmmword_739CBE0) |
| +248 | Level* (через +5*8=40) |
| +264 | `std::string` nameTag |
| +328 | `SynchedActorDataEntityWrapper` |
| +356 | byte |
| +680 | `HashedString` — identifier |
| +1184 | int spinAttackTimer (из `startSpinAttack`) |

**Ключевые поля Mob** (дополнительно к Actor):
| Смещение | Поле/Тип |
|----------|----------|
| +1308 | float/int × 4 — движение/AI state |
| +1332 | ptr (MoveControl?) |
| +1360 | `CompassSpriteCalculator` (спавн-компас) |
| +1472 | `CompassSpriteCalculator` (death compass) |
| +1584 | `ClockSpriteCalculator` |
| +1636 | float × 2 (0x3CA3D70A, 1.0f) |

**Ключевые поля Player** (дополнительно к Mob):
| Смещение | Поле/Тип |
|----------|----------|
| +2160 | `PlayerInventory*` (*(this+270)*8) |
| +3008 | ItemStack padding |
| +3024 | `ItemStack` (current item?) |
| +3184 | byte -1 (slot?) |
| +3188 | int -1 |
| +3648 | ptr (game mode?) |
| +3888 | `PlayerUIContainer` (in-place, 53 слота) |
| +7696 | ~tail |

### Другие классы

```
Level:       max_offset ≈ 8368  → sizeof(Level) ≥ 8376 байт
BlockSource: max_offset ≈ 256   → sizeof(BlockSource) ≥ 264 байт
```

**BlockSource fields** (из конструктора):
| Смещение | Поле/Тип |
|----------|----------|
| +0 | vtable |
| +8 | ? |
| +16 | ChunkSource* |
| +24 | Level* |
| +32 | byte isHosting, byte isInWaterEnabled |
| +40 | Level* (Level ptr) |
| +48 | ChunkSource* |
| +56 | Dimension* |
| +64 | Dimension::Height (short) |
| +66 | Dimension::MinHeight (short) |
| +96 | byte (isClientSide?) |
| +136 | uint64 threadId (pthread_self) |
| +144 | byte |
| +200 | byte (dimension flags from Dimension+248) |

---

## Полезные данные: аллокации приватных объектов

> Из `operator new(N)` с типом — позволяют восстановить sizeof без отладочных символов.

| Класс | sizeof |
|-------|--------|
| `ActorDefinitionDiffList` | 328 |
| `ActorPermutationEventHandler` | 120 |
| `SpatialActorNetworkData` | 120 |
| `PredictedMovementComponent` | 128 |
| `AddActorPacket` | 392 |
| `AddPlayerPacket` | 1472 |
| `SurvivalMode` | 184 / 240 (2 варианта?) |
| `LegacyBodyControl` | 16 |
| `EnderChestContainer` | 216 |
| `Random` | 2584 |
| `ListTag` | 40 |
| `CompoundTag` | 32 |
| `EconomyTradeableComponent` | 96 |
| `JumpControl` | 8 |
| `MoveControl` | 8 |
| `GlideMoveControl` | 40 |
| `HopMoveControl` | 16 |
| `DolphinMoveControl` | 16 |
| `SlimeMoveControl` | 16 |
| `LookControl` | 8 |
| `BodyControl` | 16 |
| `BlockPalette` | 120 |
| `BlockDescriptor` | 104 |
| `BlockDefinition` | 496 |
| `VillageManager` | 344 |
| `PortalForcer` | 2672 |
| `MinecraftGraphics` | 392 |
| `SceneStack` | 360 |
| `OceanMonumentFeature` | 440 |
| `OceanRuinFeature` | 424 |
| `LevelChunkBuilderData` | 264 |
| `ItemStackNetManagerServer` | 208 |
| `ConduitWindModel` | 992 |
| `ConduitCageModel` | 992 |
| `ActorResourceDefinition` | 808 |
| `DlcId` | 160 |

---

## Полезные данные: интерфейсы (из non-virtual thunks)

### BlockSource реализует:
- `IBlockSource` / `IConstBlockSource` (via thunks `containsAnyLiquid`, `containsMaterial`)
- Уведомляет через `Level::onSourceCreated` / `onSourceDestroyed`
- Диспетчеризует `BlockSource::fetchEntities`, `fetchActors`, `fetchActorIds`

### Level реализует (multiple inheritance, с non-virtual thunks):
- `ILevel` / `IConstLevel`
- `getBiomeComponentFactory`, `getBiomeRegistry`, `getBlockPalette`
- `getDimensionFactory`, `getFeatureRegistry`, `getStructureManager`
- `onSourceCreated`, `onSourceDestroyed`

### Dimension реализует:
- `serialize` / `deserialize` (CompoundTag)
- `onBlockChanged`
- `onLevelDestruction`

### JNI-специфика (из Bedrock.c):
- `Bedrock::JStringToString` — конвертация jstring → std::string
- `Bedrock::JVMAttacher::operator _JNIEnv*()` — получение JNI env
- `Bedrock::JavaClassLoader::findClass()` — загрузка Java классов
- vtable Level offset `+2944` → `isServerSide()` или подобное
- vtable Level offset `+2912` → `ChunkSource::addListener(BlockSource*)`
