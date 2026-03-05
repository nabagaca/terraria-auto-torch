# Auto Torch

Automatically places torches in dark areas while you play.

This mod was spun out from the Auto Torch feature in **QuickKeys** and adapted to brightness-triggered behavior.

## Credits

- Original Auto Torch implementation inspiration: **QuickKeys** by Inidar1
- GitHub: https://github.com/Inidar1/terraria-modder
- Nexus Mods: https://www.nexusmods.com/terraria/mods/143

## Features

- Places torches automatically when local brightness is below a configurable threshold.
- Optional hotkey toggle to enable/disable auto-placement at runtime.
- Avoids changing your currently held item while placing torches.
- Prefers placement near the player and de-prioritizes spots near existing torches.
- Optional debug-only chat messages for placement diagnostics.

## Installation

1. Download the latest release `.zip` from the GitHub Releases page.
2. Extract the zip contents.
3. Copy the `auto-torch` mod folder (containing `auto-torch.dll` and `manifest.json`) into:
   `C:\Program Files (x86)\Steam\steamapps\common\Terraria\TerrariaModder\mods\`

## Documentation

- Build and deployment: [docs/build.md](docs/build.md)
- Configuration: [docs/configuration.md](docs/configuration.md)

## Disclosure

OpenAI Codex 5.3 was used to assist with development of this project.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
