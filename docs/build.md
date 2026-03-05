# Build and Deployment

## Build

```powershell
dotnet build terraria_auto_torch.sln -c Release
```

## Default deploy behavior

By default, the build is configured to deploy:

- `auto-torch.dll`
- `manifest.json`

to:

`C:\Program Files (x86)\Steam\steamapps\common\Terraria\TerrariaModder\mods\auto-torch`

## Disable deploy for a build

```powershell
dotnet build terraria_auto_torch.sln -c Release -p:EnableTerrariaModderDeploy=false
```
