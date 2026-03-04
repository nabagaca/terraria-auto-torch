using Terraria;
using TerrariaModder.Core;
using TerrariaModder.Core.Logging;

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

        public void Initialize(ModContext context)
        {
            _log = context.Logger;
            _context = context;

            // Register our keybind
            context.RegisterKeybind("show-greeting", "Show Greeting",
                "Display the greeting message", "G", ShowGreeting);

            _log.Info("My First Mod initialized!");
        }

        public void OnWorldLoad()
        {
            // Check if we should show greeting on world enter
            bool showOnEnter = _context.Config?.Get<bool>("show_on_enter") ?? true;

            if (showOnEnter)
            {
                ShowGreeting();
            }
        }

        public void OnWorldUnload()
        {
            _log.Debug("World unloading");
        }

        public void Unload()
        {
            _log.Info("My First Mod unloading");
        }

        // Optional: Implement this to receive config changes without restart
        public void OnConfigChanged()
        {
            _log.Info("Config changed - reloading settings");
            // Re-read any cached config values here
        }

        private void ShowGreeting()
        {
            // Get the greeting from config, or use default
            string greeting = _context.Config?.Get<string>("greeting") ?? "Hello, Terraria!";

            // Show it in the game chat
            Main.NewText(greeting, 255, 255, 100); // Yellow text

            _log.Info($"Showed greeting: {greeting}");
        }
    }
}