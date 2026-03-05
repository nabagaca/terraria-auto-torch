# Configuration

Config is stored in the mod's `config.json` and exposed through Terraria Modder's config UI.

## Settings

- `enabled`:
  Master on/off for the mod.
- `showMessages`:
  Shows user-facing messages (for example, toggle enabled/disabled).
- `showDebugMessages`:
  Shows debug placement messages (for example, no valid spot found).
- `brightnessLevelTrigger`:
  Brightness percentage (`0-100`) below which auto placement can trigger.
- `brightnessCheckCooldownTicks`:
  How often brightness is checked in ticks (`60` ticks is about `1` second).
- `nearbyTorchPenaltyRadiusTiles`:
  Radius in tiles used to detect nearby torches during candidate scoring.
- `nearbyTorchScorePenalty`:
  Score penalty applied to candidates near existing torches.
