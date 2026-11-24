using UnrealBuildTool;

public class BarrioWorld : ModuleRules
{
	public BarrioWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "BarrioCore" });
	}
}
