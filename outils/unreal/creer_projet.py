"""Crée le projet Unreal Engine d'Atelya (le « studio »), vide, prêt à recevoir les paquets des maquettes (11/11/2026).

    python outils/unreal/creer_projet.py [dossier]      (défaut : D:\\Atelya-Unreal\\AtelyaStudio)

Pourquoi un chemin SANS accent : plusieurs outils d'Unreal (compilateur d'effets, fichiers temporaires) gèrent mal les chemins
accentués, comme OpenCV (piège connu du projet : « Modélisation immobilière »).
Un projet Unreal n'est qu'un fichier .uproject (la liste des greffons) et des réglages (Config\\*.ini) : rien à installer.
Réglages choisis (cinématique réaliste d'un intérieur, éclairage entièrement calculé en direct, rien de « précalculé ») :
- Lumen pour la lumière indirecte et les reflets (la lumière qui rebondit sur les murs et le parquet), calculé par les
  rayons de la carte graphique (« ray tracing matériel », RTX) : le calcul « logiciel » laissait des traînées en éventail
  sur les murs d'une chambre éclairée par une seule fenêtre (essai du 11/11/2026) ;
- ombres virtuelles (nettes de près comme de loin) ; pas d'éclairage statique (on n'a jamais à « cuire » la lumière) ;
- DirectX 12 en SM6 (le jeu d'effets récent : sans lui, pas de rayons ; en SM5 le « ray tracing » est ignoré
  sans erreur, vu le 11/11/2026) ; exposition automatique coupée (réglée par Atelya, comme le « photographe » de Blender) ;
- unités : Unreal compte en centimètres ;
- « custom stencil » actif (r.CustomDepth=3) : les murs et plafonds y sont marqués, c'est le masque que regarde le
  photographe d'Atelya pour régler l'exposition (moteur/photographe.py) ;
- « Remote Execution » de Python (sur cette machine seulement, 127.0.0.1) : le MCP de développement (runreal/unreal-mcp)
  pilote l'éditeur ouvert. Il ne sert qu'à Claude pendant le développement, jamais au produit.
"""
import json
import sys
from pathlib import Path

DOSSIER_DEFAUT = Path(r"D:\Atelya-Unreal\AtelyaStudio")
NOM = "AtelyaStudio"
VERSION_MOTEUR = "5.8"

GREFFONS = ["PythonScriptPlugin", "EditorScriptingUtilities", "SequencerScripting", "MovieRenderPipeline", "Interchange",
            "InterchangeEditor", "InterchangeAssets"]

DEFAULT_ENGINE = """[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
-D3D12TargetedShaderFormats=PCD3D_SM5
+D3D12TargetedShaderFormats=PCD3D_SM6

[/Script/Engine.RendererSettings]
r.DynamicGlobalIlluminationMethod=1
r.ReflectionMethod=1
r.Shadow.Virtual.Enable=1
r.GenerateMeshDistanceFields=True
r.AllowStaticLighting=False
r.DefaultFeature.AutoExposure=False
r.DefaultFeature.MotionBlur=False
r.Lumen.TraceMeshSDFs=1
r.AntiAliasingMethod=4
r.RayTracing=True
r.Lumen.HardwareRayTracing=True
r.SkinCache.CompileShaders=True
r.RayTracing.Shadows=False
r.CustomDepth=3

[/Script/UnrealEd.EditorPerformanceSettings]
bThrottleCPUWhenNotForeground=False

[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
bRemoteExecution=True
RemoteExecutionMulticastBindAddress=127.0.0.1
"""

DEFAULT_GAME = """[/Script/EngineSettings.GeneralProjectSettings]
ProjectName=Atelya Studio
Description=Cinematiques et visites des logements construits par Atelya
"""


def creer(dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "Config").mkdir(exist_ok=True)
    (dossier / "Content").mkdir(exist_ok=True)
    projet = {"FileVersion": 3, "EngineAssociation": VERSION_MOTEUR, "Category": "", "Description": "Atelya : studio Unreal",
              "Plugins": [{"Name": g, "Enabled": True} for g in GREFFONS]}
    chemin = dossier / f"{NOM}.uproject"
    chemin.write_text(json.dumps(projet, indent=1), encoding="utf-8")
    (dossier / "Config" / "DefaultEngine.ini").write_text(DEFAULT_ENGINE, encoding="utf-8")
    (dossier / "Config" / "DefaultGame.ini").write_text(DEFAULT_GAME, encoding="utf-8")
    return chemin


if __name__ == "__main__":
    print(creer(Path(sys.argv[1]) if len(sys.argv) > 1 else DOSSIER_DEFAUT))
