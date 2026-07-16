using System;
using System.Collections.Generic;
using System.Net;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RacingDSX
{
    public class Program
    {
        public const string VERSION = "0.6.7-headless";

        static void Main(string[] args)
        {
            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                switch (arg)
                {
                    case "-v":
                        Console.WriteLine($"RacingDSX v{VERSION}");
                        return;
                }
            }

            RunHeadless();
        }

        static void RunHeadless()
        {
            Console.WriteLine($"RacingDSX v{VERSION} (Headless Mode)");
            Console.WriteLine("Loading configuration...");

            // Load config
            var config = Config.ConfigHandler.GetConfig();
            Console.WriteLine($"DisableAppCheck: {config.DisableAppCheck}");
            Console.WriteLine($"DSXPort: {config.DSXPort}");
            Console.WriteLine($"DefaultProfile: {config.DefaultProfile}");

            // Set active profile from default (bypass GUI selection)
            if (config.DefaultProfile != null && config.Profiles.ContainsKey(config.DefaultProfile))
            {
                config.ActiveProfile = config.Profiles[config.DefaultProfile];
                Console.WriteLine($"ActiveProfile set to: {config.ActiveProfile.Name}");
                Console.WriteLine($"  GameType: {config.ActiveProfile.GameType}");
                Console.WriteLine($"  gameUDPPort: {config.ActiveProfile.gameUDPPort}");
            }
            else
            {
                Console.WriteLine($"No active profile found for DefaultProfile='{config.DefaultProfile}'");
                Console.WriteLine($"Available profiles: {string.Join(", ", config.Profiles.Keys)}");
                return;
            }

            // Ensure DisableAppCheck is true in headless mode
            config.DisableAppCheck = true;

            // Create progress reporter that writes to console
            IProgress<RacingDSXWorker.RacingDSXReportStruct> reporter = new Progress<RacingDSXWorker.RacingDSXReportStruct>(r =>
            {
                Console.WriteLine($"[RacingDSX] {r.message}");
            });

            // Create and start the worker
            Console.WriteLine("Starting RacingDSX worker...");
            var worker = new RacingDSXWorker(config, reporter);

            // Run synchronously (blocks until stopped)
            worker.Run();

            Console.WriteLine("RacingDSX worker stopped.");
        }
    }

    public class ParametersConverter : JsonConverter<object[]>
    {
        public override object[] Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        {
            if (reader.TokenType != JsonTokenType.StartArray)
            {
                throw new JsonException("Expected start of array");
            }

            var parameters = new List<object>();
            reader.Read();

            while (reader.TokenType != JsonTokenType.EndArray)
            {
                switch (reader.TokenType)
                {
                    case JsonTokenType.Number:
                        if (reader.TryGetInt32(out int intValue))
                            parameters.Add(intValue);
                        else if (reader.TryGetDouble(out double doubleValue))
                            parameters.Add(doubleValue);
                        break;
                    case JsonTokenType.String:
                        string stringValue = reader.GetString();
                        if (Enum.TryParse<Trigger>(stringValue, out var trigger))
                            parameters.Add((int)trigger);
                        else if (Enum.TryParse<TriggerMode>(stringValue, out var triggerMode))
                            parameters.Add((int)triggerMode);
                        else if (Enum.TryParse<CustomTriggerValueMode>(stringValue, out var customTrigger))
                            parameters.Add((int)customTrigger);
                        else if (Enum.TryParse<PlayerLEDNewRevision>(stringValue, out var playerLed))
                            parameters.Add((int)playerLed);
                        else if (Enum.TryParse<MicLEDMode>(stringValue, out var micLed))
                            parameters.Add((int)micLed);
                        else
                            parameters.Add(stringValue);
                        break;
                    case JsonTokenType.True:
                    case JsonTokenType.False:
                        parameters.Add(reader.GetBoolean());
                        break;
                    case JsonTokenType.Null:
                        parameters.Add(null);
                        break;
                }
                reader.Read();
            }

            return parameters.ToArray();
        }

        public override void Write(Utf8JsonWriter writer, object[] value, JsonSerializerOptions options)
        {
            writer.WriteStartArray();
            // Skip controllerIndex (first element) — Hefesto expects [side, mode, ...]
            int startIdx = value.Length > 0 && value[0] is int ? 1 : 0;
            for (int i = startIdx; i < value.Length; i++)
            {
                var item = value[i];
                if (item == null)
                {
                    writer.WriteNullValue();
                    continue;
                }

                // Hefesto expects "side" as string ("left"/"right") and "mode" as string ("Resistance", etc.)
                if (item is Trigger trigger)
                {
                    writer.WriteStringValue(trigger.ToString().ToLowerInvariant());
                }
                else if (item is TriggerMode mode)
                {
                    writer.WriteStringValue(mode.ToString());
                }
                else if (item is CustomTriggerValueMode customMode)
                {
                    writer.WriteNumberValue((int)customMode);
                }
                else if (item is int intValue)
                {
                    writer.WriteNumberValue(intValue);
                }
                else if (item is double doubleValue)
                {
                    writer.WriteNumberValue(doubleValue);
                }
                else if (item is string stringValue)
                {
                    writer.WriteStringValue(stringValue);
                }
                else if (item is bool boolValue)
                {
                    writer.WriteBooleanValue(boolValue);
                }
                else if (item is Enum enumValue)
                {
                    writer.WriteStringValue(enumValue.ToString());
                }
                else
                {
                    writer.WriteNumberValue(Convert.ToInt32(item));
                }
            }
            writer.WriteEndArray();
        }
    }

    public static class Triggers
    {
        public static IPAddress localhost = new IPAddress(new byte[] { 127, 0, 0, 1 });

        private static readonly JsonSerializerOptions jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false,
            Converters = { new ParametersConverter() }
        };

        public static string PacketToJson(Packet packet)
        {
            return JsonSerializer.Serialize(packet, jsonOptions);
        }

        public static Packet JsonToPacket(string json)
        {
            return JsonSerializer.Deserialize<Packet>(json, jsonOptions)
                ?? throw new InvalidOperationException("Deserialized packet is null");
        }
    }

    public enum TriggerMode
    {
        Normal = 0, GameCube = 1, VerySoft = 2, Soft = 3, Hard = 4, VeryHard = 5,
        Hardest = 6, Rigid = 7, VibrateTrigger = 8, Choppy = 9, Medium = 10,
        VibrateTriggerPulse = 11, CustomTriggerValue = 12, Resistance = 13,
        Bow = 14, Galloping = 15, SemiAutomaticGun = 16, AutomaticGun = 17,
        Machine = 18, OFF = 19, FEEDBACK = 20, WEAPON = 21, VIBRATION = 22,
        SLOPE_FEEDBACK = 23, MULTIPLE_POSITION_FEEDBACK = 24,
        MULTIPLE_POSITION_VIBRATION = 25, VIBRATE_TRIGGER_10Hz = 26
    }

    public enum CustomTriggerValueMode
    {
        OFF = 0, Rigid = 1, RigidA = 2, RigidB = 3, RigidAB = 4,
        Pulse = 5, PulseA = 6, PulseB = 7, PulseAB = 8,
        VibrateResistance = 9, VibrateResistanceA = 10, VibrateResistanceB = 11,
        VibrateResistanceAB = 12, VibratePulse = 13, VibratePulseA = 14,
        VibratePulsB = 15, VibratePulseAB = 16
    }

    public enum Trigger { Invalid, Left, Right }

    public enum InstructionType
    {
        Invalid, TriggerUpdate, RGBUpdate, PlayerLED, PlayerLEDNewRevision,
        MicLED, TriggerThreshold, ResetToUserSettings, GetDSXStatus
    }

    public enum PlayerLEDNewRevision { One, Two, Three, Four, Five }
    public enum MicLEDMode { Off, On, Pulse }

    public class InstructionTypeStringConverter : JsonConverter<InstructionType>
    {
        public override InstructionType Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        {
            string value = reader.GetString() ?? "Invalid";
            if (Enum.TryParse<InstructionType>(value, true, out var result))
                return result;
            return InstructionType.Invalid;
        }

        public override void Write(Utf8JsonWriter writer, InstructionType value, JsonSerializerOptions options)
        {
            writer.WriteStringValue(value.ToString());
        }
    }

    public class Instruction
    {
        [JsonConstructor]
        public Instruction(InstructionType type) => Type = type;

        [JsonPropertyName("type")]
        [JsonConverter(typeof(InstructionTypeStringConverter))]
        public InstructionType Type { get; set; }

        [JsonPropertyName("parameters")]
        [JsonConverter(typeof(ParametersConverter))]
        public object[] Parameters { get; set; }
    }

    public class Packet
    {
        [JsonPropertyName("version")]
        public int Version { get; set; } = 1;

        [JsonPropertyName("instructions")]
        public Instruction[] Instructions { get; set; } = Array.Empty<Instruction>();
    }
}
