using UnrealBuildTool;

public class BarrioTarget : TargetRules
{
	public BarrioTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "Barrio", "BarrioCore", "BarrioCombat", "BarrioCharacters", "BarrioWorld", "BarrioOnline", "BarrioUI" });
	}
}
