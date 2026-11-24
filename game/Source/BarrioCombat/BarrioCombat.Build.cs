using UnrealBuildTool;

public class BarrioCombat : ModuleRules
{
	public BarrioCombat(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "BarrioCore" });
	}
}
