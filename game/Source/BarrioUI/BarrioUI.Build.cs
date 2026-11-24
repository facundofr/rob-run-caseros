using UnrealBuildTool;

// La UI puede leer de los demás sistemas; ningún sistema depende de la UI.
public class BarrioUI : ModuleRules
{
	public BarrioUI(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "BarrioCore", "BarrioCharacters", "BarrioCombat" });
	}
}
