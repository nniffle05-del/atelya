// Lance un script Python dans l'ÉDITEUR Unreal OUVERT (Remote Execution de Python, sur ce PC seulement : 127.0.0.1), comme le
// ferait le MCP de développement (même bibliothèque, unreal-remote-execution, MIT, outils de développement installés avec
// l'accord de NT le 11/11/2026). Utilisé par outils/unreal/cinematique_unreal.py quand l'éditeur est ouvert (il verrouille alors
// les fichiers du projet : la ligne de commande sans écran ne peut plus les enregistrer).
//
//     node editeur_python.js <script.py> [arguments…]
//
// Le script reçoit ses arguments dans sys.argv (comme avec -run=pythonscript). Sortie : ce que le script affiche ; code 1 si
// le script lève une erreur ou si l'éditeur ne répond pas.
const path = require("path");
const fs = require("fs");
const BIBLIOTHEQUE = process.env.UE_REMOTE_EXECUTION ||
  "D:/Atelya-Unreal/outils/mcp-unreal/node_modules/unreal-remote-execution";
const ure = require(BIBLIOTHEQUE);

(async () => {
  const [script, ...args] = process.argv.slice(2);
  const chemin = path.resolve(script).replace(/\\/g, "/");
  const code = [
    "import sys",
    `sys.argv = ${JSON.stringify([chemin, ...args])}`,
    `exec(compile(open(${JSON.stringify(chemin)}, encoding="utf-8").read(), ${JSON.stringify(chemin)}, "exec"), {"__name__": "__main__"})`,
  ].join("\n");
  const re = new ure.RemoteExecution(new ure.RemoteExecutionConfig(1, ["239.0.0.1", 6766], "127.0.0.1"));
  await re.start();
  const noeud = await re.getFirstRemoteNode(1000, 15000);
  await re.openCommandConnection(noeud);
  const r = await re.runCommand(code);
  for (const o of r.output || []) {
    if (o.type === "Warning" && /DeprecationWarning/.test(o.output)) continue;
    process.stdout.write((o.type === "Error" ? "LogPython: Error: " : "") + o.output);
  }
  if (!r.success) console.log("LogPython: Error: " + r.result);
  re.stop();
  process.exit(r.success ? 0 : 1);
})().catch((e) => { console.error("LogPython: Error: éditeur injoignable : " + ((e && e.message) || e)); process.exit(1); });
