using UnrealBuildTool;

public class BarrioEditorTarget : TargetRules
{
	public BarrioEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "Barrio", "BarrioCore", "BarrioCombat", "BarrioCharacters", "BarrioWorld", "BarrioUI" });
	}
}
