using UnrealBuildTool;

// Tipos compartidos por todos los sistemas. No depende de ningún otro módulo del juego.
public class BarrioCore : ModuleRules
{
	public BarrioCore(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
	}
}
