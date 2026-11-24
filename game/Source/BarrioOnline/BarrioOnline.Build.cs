using UnrealBuildTool;

// Comunicación con el backend (cuentas, sesiones, economía, registro de servidores).
public class BarrioOnline : ModuleRules
{
	public BarrioOnline(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "DeveloperSettings", "BarrioCore" });
		PrivateDependencyModuleNames.AddRange(new string[] { "HTTP", "Json" });
	}
}
