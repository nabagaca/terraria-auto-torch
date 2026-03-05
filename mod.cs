using Terraria;
using TerrariaModder.Core;
using TerrariaModder.Core.Logging;

using System;
using System.Collections.Generic;
using Terraria.ID;
using Terraria.UI;
using Microsoft.Xna.Framework;
using TerrariaModder.Core.Events;

namespace AutoTorch
{
    public class Mod : IMod
    {
        // These must match manifest.json
        public string Id => "auto-torch";
        public string Name => "Auto Torch";
        public string Version => "0.1.0";

        private ILogger _log;
        private ModContext _context;

        private bool _enabled;
        private bool _autoPlaceEnabled;
        private bool _showMessages;
        private int _brightnessLevelTrigger;
        private float _brightnessThreshold;
        private ulong _nextAutoPlaceTick;
        private const ulong AutoPlaceCooldownTicks = 30;

        private static bool _placingTorch = false;

        private void LoadConfig()
        {
            _enabled = _context.Config.Get<bool>("enabled");
            _showMessages = _context.Config.Get<bool>("showMessages");
            _brightnessLevelTrigger = _context.Config.Get("brightnessLevelTrigger", 50);
            _brightnessLevelTrigger = Math.Max(0, Math.Min(100, _brightnessLevelTrigger));
            _brightnessThreshold = _brightnessLevelTrigger / 100f;

            // Enable debug logging if configured
            bool debugLogging = _context.Config.Get("debugLogging", false);
            if (debugLogging)
            {
                _log.MinLevel = LogLevel.Debug;
            }
        }

        public void Initialize(ModContext context)
        {
            _log = context.Logger;
            _context = context;
            _autoPlaceEnabled = true;

            LoadConfig();

            // Register our keybind
            context.RegisterKeybind("toggle-placement", "Toggle Auto Torch Placement", "Toggle automatic torch placement on/off", "OemTilde", toggleAutoPlace);

            if (!_enabled)
            {
                _log.Info("Auto Torch is disabled in config (keybinds registered but inactive)");
                return;
            }

            // Subscribe to post-update for item restoration
            FrameEvents.OnPostUpdate += OnPostUpdate;

            _log.Info("Auto Torch initialized");
        }

        private void toggleAutoPlace()
        {
            _autoPlaceEnabled = !_autoPlaceEnabled;
            string status = _autoPlaceEnabled ? "enabled" : "disabled";
            ShowMessage($"Auto torch placement {status}", 255, 255, 0);
        }

        private void ShowMessage(string message, byte r = 255, byte g = 255, byte b = 0)
        {
            if (!_showMessages) return;
            try
            {
                Main.NewText($"[Auto Torch] {message}", r, g, b);
            }
            catch { }
        }

        public void OnWorldLoad()
        {
            _log.Debug("World loaded");
        }

        public void OnWorldUnload()
        {
            _log.Debug("World unloading");
        }

        public void Unload()
        {
            FrameEvents.OnPostUpdate -= OnPostUpdate;
            _placingTorch = false;
            _log.Info("Auto Torch unloaded");
        }

        public void OnConfigChanged()
        {
            LoadConfig();
        }

        private void OnPostUpdate()
        {
            try
            {
                if (_enabled && _autoPlaceEnabled && !Main.gameMenu)
                {
                    Player player = Main.player[Main.myPlayer];
                    if (player != null)
                        TryAutoPlaceFromBrightness(player);
                }
            }
            catch { }
        }

        private void TryAutoPlaceFromBrightness(Player player)
        {
            if (player.dead || player.ghost) return;
            if (Main.playerInventory || Main.mapFullscreen) return;
            if (player.itemAnimation > 0 || !player.ItemTimeIsZero || player.reuseDelay > 0) return;
            if (_placingTorch) return;

            ulong currentTick = Main.GameUpdateCount;
            if (currentTick < _nextAutoPlaceTick) return;

            int tileX = (int)(player.Center.X / 16f);
            int tileY = (int)(player.Center.Y / 16f);
            Color lightColor = Lighting.GetColor(tileX, tileY);

            // Relative luminance, normalized from 0.0 to 1.0.
            float brightness =
                (0.2126f * lightColor.R + 0.7152f * lightColor.G + 0.0722f * lightColor.B) / 255f;

            if (brightness <= _brightnessThreshold)
            {
                _nextAutoPlaceTick = currentTick + AutoPlaceCooldownTicks;
                AutoPlaceTorch();
            }
        }

        private void AutoPlaceTorch()
        {
            if (!_enabled) return;
            if (!_autoPlaceEnabled) return;
            if (_placingTorch) return;
            _placingTorch = true;

            try
            {
                Player player = Main.player[Main.myPlayer];
                if (player == null) return;

                Item[] inventory = player.inventory;
                if (inventory == null) return;

                // Get torch set
                bool[] torchSet = TileID.Sets.Torches;
                if (torchSet == null) return;

                // Find a torch in inventory (must have stack > 0)
                int torchSlot = -1;
                Item torchItem = null;
                int torchTileType = -1;
                int torchPlaceStyle = 0;

                for (int i = 0; i < inventory.Length; i++)
                {
                    Item item = inventory[i];
                    if (item.stack <= 0) continue; // Skip empty or depleted slots

                    int createTile = item.createTile;
                    if (createTile >= 0 && createTile < torchSet.Length && torchSet[createTile])
                    {
                        torchSlot = i;
                        torchItem = item;
                        torchTileType = createTile;
                        torchPlaceStyle = item.placeStyle;
                        break;
                    }
                }

                if (torchSlot == -1 || torchItem == null)
                {
                    ShowMessage("No torches in inventory!", 255, 255, 0);
                    return;
                }

                // Get player position
                Vector2 pos = player.position;
                int width = player.width;
                int height = player.height;

                // Set initial tile target to player center
                int centerX = (int)((pos.X + width / 2f) / 16f);
                int centerY = (int)((pos.Y + height / 2f) / 16f);
                Player.tileTargetX = centerX;
                Player.tileTargetY = centerY;

                // Get tile ranges
                int tileRangeX = Math.Min(Player.tileRangeX, 50);
                int tileRangeY = Math.Min(Player.tileRangeY, 50);
                int blockRange = player.blockRange;

                // Build list of positions sorted by distance from mouse
                Vector2 mouseWorld = Main.MouseWorld;
                float mouseX = mouseWorld.X;
                float mouseY = mouseWorld.Y;
                // If mouse is 0,0, use player center
                if (mouseX == 0 && mouseY == 0)
                {
                    mouseX = pos.X + width / 2f;
                    mouseY = pos.Y + height / 2f;
                }

                var targets = new List<Tuple<float, int, int>>();
                int minX = -tileRangeX - blockRange + (int)(pos.X / 16f) + 1;
                int maxX = tileRangeX + blockRange - 1 + (int)((pos.X + width) / 16f);
                int minY = -tileRangeY - blockRange + (int)(pos.Y / 16f) + 1;
                int maxY = tileRangeY + blockRange - 2 + (int)((pos.Y + height) / 16f);

                for (int j = minX; j <= maxX; j++)
                {
                    for (int k = minY; k <= maxY; k++)
                    {
                        float dist = (float)Math.Sqrt((mouseX - j * 16f) * (mouseX - j * 16f) + (mouseY - k * 16f) * (mouseY - k * 16f));
                        targets.Add(new Tuple<float, int, int>(dist, j, k));
                    }
                }
                targets.Sort((a, b) => a.Item1.CompareTo(b.Item1));

                // Try each position using direct tile placement
                bool placeSuccess = false;

                foreach (var target in targets)
                {
                    int tileX = target.Item2;
                    int tileY = target.Item3;

                    // Get tile state before
                    Tile tile = Main.tile[tileX, tileY];
                    bool hadTileBefore = tile != null && tile.active();

                    Player.tileTargetX = tileX;
                    Player.tileTargetY = tileY;

                    // Use direct WorldGen.PlaceTile with correct tile type and style
                    if (!hadTileBefore)
                    {
                        try
                        {
                            bool placed = WorldGen.PlaceTile(tileX, tileY, torchTileType, false, false, Main.myPlayer, torchPlaceStyle);
                            if (placed)
                            {
                                // Consume one torch from inventory
                                if (torchItem.stack > 0)
                                {
                                    torchItem.stack--;
                                    if (torchItem.stack <= 0)
                                        torchItem.TurnToAir();
                                }
                                placeSuccess = true;
                                break;
                            }
                        }
                        catch
                        {
                            // Continue trying other positions
                        }
                    }
                }

                if (!placeSuccess)
                    ShowMessage("No valid spot for torch", 255, 255, 0);
            }
            catch (Exception ex)
            {
                _log.Error($"Auto-torch error: {ex.Message}");
                _log.Error($"Stack: {ex.StackTrace}");
            }
            finally
            {
                _placingTorch = false;
            }
        }
    }
}
