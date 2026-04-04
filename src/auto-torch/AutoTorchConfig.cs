using TerrariaModder.Core.Config;

namespace AutoTorch
{
    public class AutoTorchConfig : ModConfig
    {
        public override int Version => 1;

        [Client, Label("Enabled"), Description("Master toggle for auto-torch.")]
        public bool Enabled { get; set; } = true;

        [Client, Label("Show Messages"), Description("Display chat notifications when using auto-torch.")]
        [FormerlySerializedAs("showMessages")]
        public bool ShowMessages { get; set; } = false;

        [Client, Label("Show Debug Messages"), Description("Show debug-only auto-torch messages such as placement failures.")]
        [FormerlySerializedAs("showDebugMessages")]
        public bool ShowDebugMessages { get; set; } = false;

        [Client, Range(0, 100), Label("Brightness Percentage Trigger"), Description("The brightness percentage below which torches are placed (0-100)")]
        [FormerlySerializedAs("brightnessLevelTrigger")]
        public int BrightnessLevelTrigger { get; set; } = 50;

        [Client, Range(0, 600), Label("Brightness Check Cooldown (Ticks)"), Description("How often to check brightness. 60 ticks is about 1 second.")]
        [FormerlySerializedAs("brightnessCheckCooldownTicks")]
        public int BrightnessCheckCooldownTicks { get; set; } = 30;

        [Client, Range(0, 20), Label("Nearby Torch Penalty Radius"), Description("Radius in tiles used to detect nearby torches when scoring placement.")]
        [FormerlySerializedAs("nearbyTorchPenaltyRadiusTiles")]
        public int NearbyTorchPenaltyRadiusTiles { get; set; } = 4;

        [Client, Range(0, 10000), Label("Nearby Torch Penalty Strength"), Description("How strongly to avoid candidate spots near other torches.")]
        [FormerlySerializedAs("nearbyTorchScorePenalty")]
        public float NearbyTorchScorePenalty { get; set; } = 1000f;

        [Client, Label("Debug Logging"), Description("Enable debug-level logging output for auto-torch internals.")]
        [FormerlySerializedAs("debugLogging")]
        public bool DebugLogging { get; set; } = false;
    }
}
