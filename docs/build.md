# Build and Deployment

## Build

TerrariaModder is pinned as a Git submodule at `dependencies/terraria-modder`.
Initialize it after cloning:

```powershell
git submodule update --init --recursive
```

Run the framework's setup once to link your installed Terraria files:

```powershell
Push-Location dependencies/terraria-modder
.\setup.bat
Pop-Location
```

Then build from this repository's root:

```powershell
dotnet build src/auto-torch/auto-torch.csproj -c Release
```

## Package without publishing

```powershell
python Build-and-Upload.py --skip-upload --skip-github
```

This builds the mod and refreshes `artifacts/auto-torch-v<version>.zip` with an
`auto-torch/` folder containing the DLL and manifest. Local packaging does not
require credentials.
The publishing options and destinations retain their existing behavior.
`--skip-build` reuses an existing versioned ZIP, or packages the existing build
outputs when that ZIP is absent.

## Default deploy behavior

By default, the build is configured to deploy:

- `auto-torch.dll`
- `manifest.json`

to:

`C:\Program Files (x86)\Steam\steamapps\common\Terraria\TerrariaModder\mods\auto-torch`

## Disable deploy for a build

```powershell
dotnet build src/auto-torch/auto-torch.csproj -c Release -p:EnableTerrariaModderDeploy=false
```

## Terraria 1.4.5.8 compatibility

Build against Terraria 1.4.5.8 and a current TerrariaModder checkout. The released
0.4.0 DLL references `Item.TurnToAir(bool)`, while Terraria 1.4.5.8 exposes
`Item.TurnToAir()`. Although the source call looks the same because the old
argument was optional, the old DLL fails JIT compilation of `AutoPlaceTorch`
with `MissingMethodException` before it can place anything. The former empty
catch in `OnPostUpdate` hid that error.

The 0.4.1 DLL has been rebuilt against the current API. A .NET Framework 4.8
probe using `RuntimeHelpers.PrepareMethod` reproduced the missing-method error
in 0.4.0 and successfully compiled the rebuilt placement method without executing
it. Placement has also been confirmed working in-game. Multiplayer synchronization
has not been separately verified. Inventory slots and the selected item are not
moved by placement.
