using UnrealBuildTool;

// Módulo principal: arma el juego juntando los sistemas (GameMode y reglas de la partida).
public class Barrio : ModuleRules
{
	public Barrio(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core", "CoreUObject", "Engine",
			"BarrioCore", "BarrioCombat", "BarrioCharacters", "BarrioWorld", "BarrioUI"
		});
	}
}
