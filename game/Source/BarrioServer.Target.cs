using UnrealBuildTool;

// Servidor dedicado (sin gráficos). Requiere Unreal Engine compilado desde el código fuente:
// la versión del Epic Games Launcher no incluye este tipo de build.
public class BarrioServerTarget : TargetRules
{
	public BarrioServerTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Server;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "Barrio", "BarrioCore", "BarrioCombat", "BarrioCharacters", "BarrioWorld", "BarrioUI" });
	}
}
